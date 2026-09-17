"""The vision provider adapter. The ONLY file permitted to import an SDK.

`service.py` remains the only file importing `lm_*`; this file imports neither
`lm_*` nor anything from the application. It hands back a plain callable and
knows nothing about declarations, coverage or compliance.

Three things this file deliberately does NOT do:

  * It does not parse JSON. `lm_extract.parse_vision_json` already tolerates
    markdown fences, leading prose and trailing prose, and raises on the four
    unusable shapes. Parsing here would duplicate tested behaviour and split
    the failure modes across two modules.
  * It does not retry. A retry doubles the wait with an officer standing at the
    bench, and the second attempt fails for the same reason as the first.
  * It does not write the prompt. `lm_extract.VISION_PROMPT` is written to make
    returning `null` the easy path; a prompt that pushes a model to fill every
    field turns that pressure directly into invented declarations.

Configuration is read from the environment, never from code, a form field or a
log line. The variables are namespaced `LM_VISION_*` so the application cannot
accidentally inherit unrelated provider credentials that happen to be present
on the machine.
"""
from __future__ import annotations

import base64
import io
import os
from typing import Callable, Optional

# Environment, and nothing else.
ENV_PROVIDER = "LM_VISION_PROVIDER"
ENV_KEY = "LM_VISION_API_KEY"
ENV_MODEL = "LM_VISION_MODEL"
ENV_BASE_URL = "LM_VISION_BASE_URL"

# TEMPORARY, 14 Sep. Diagnostic only, off unless set, never read during an
# inspection. Remove with _debug_hooks/_debug_exception once the 404 and the
# reported transport failure are understood.
ENV_DEBUG = "LM_VISION_DEBUG"

PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_GEMINI = "gemini"
PROVIDERS = (PROVIDER_ANTHROPIC, PROVIDER_GEMINI)

DEFAULT_MODELS = {
    PROVIDER_ANTHROPIC: "claude-opus-5",
    # NOT gemini-2.0-flash. Google still lists that model but no longer serves
    # generateContent for it to new accounts, so it 404s -- a failure mode that
    # cost two separate multi-day debugging sessions because the app swallowed
    # the provider's explanation. gemini-flash-lite-latest is confirmed working
    # against a real inline-image request. If this one is ever retired the same
    # way, `python3 diag_gemini.py --list` names the models a key can actually
    # call.
    PROVIDER_GEMINI: "gemini-flash-lite-latest",
}
DEFAULT_MODEL = DEFAULT_MODELS[PROVIDER_ANTHROPIC]      # kept: older callers
DEFAULT_BASE_URL = "https://api.anthropic.com"

# A hung request on stage is worse than a failed one.
TIMEOUT_SECONDS = 30.0

# Six short declaration strings. Large enough that a long manufacturer address
# cannot truncate the JSON, small enough to stay well inside the timeout.
MAX_TOKENS = 2048

# What the provider will accept. Anything else is converted before sending.
_NATIVE_MEDIA = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
}

# A Gemini candidate stopped for one of these carries no text part. The retired
# SDK raised an exception for them; this one does not, so they are recognised
# here and mapped onto the same message. Compared against the enum member's
# `.value`, which is exactly this name -- `str()` on it yields
# "FinishReason.SAFETY" instead, which would never match.
_DECLINED_FINISH_REASONS = {
    "SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION",
    "LANGUAGE", "IMAGE_SAFETY", "IMAGE_PROHIBITED_CONTENT", "IMAGE_RECITATION",
}


class VisionUnavailable(Exception):
    """No provider is configured, or its SDK is not installed.

    Distinct from a failure: the feature is simply absent, the button does not
    render, and the manual path is untouched.
    """


class VisionTransportError(Exception):
    """The provider could not be reached, timed out, or refused the request.

    Deliberately NOT the same as `lm_extract.ExtractionError`, which means the
    backend answered with something unusable. Six CANNOT_DETERMINE caused by a
    dead API key must not look like a bad photograph.
    """


def configured() -> Optional[dict]:
    """What is configured, or None. Never returns the key itself."""
    key = os.environ.get(ENV_KEY, "").strip()
    if not key:
        return None
    provider = os.environ.get(ENV_PROVIDER, PROVIDER_ANTHROPIC).strip().lower()
    if provider not in PROVIDERS:
        return None
    return {"provider": provider,
            "model": (os.environ.get(ENV_MODEL, "").strip()
                      or DEFAULT_MODELS[provider])}


def _media_type(data: bytes) -> tuple[bytes, str]:
    """Return (bytes, media_type) the provider accepts.

    BMP and TIFF are accepted by the upload form but not by the provider, so
    they are re-encoded losslessly to PNG. The pixels are unchanged; nothing is
    resampled, and nothing here touches the measurement path.
    """
    for magic, media in _NATIVE_MEDIA.items():
        if data.startswith(magic):
            return data, media
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return data, "image/webp"
    from PIL import Image                       # not an SDK; format conversion only
    buf = io.BytesIO()
    with Image.open(io.BytesIO(data)) as im:
        im.save(buf, format="PNG")
    return buf.getvalue(), "image/png"


def _debug(line: str) -> None:
    """TEMPORARY. One diagnostic line on stderr, never on the officer's screen."""
    import sys
    print("[vision-debug] " + line, file=sys.stderr, flush=True)


def _redact(headers) -> dict:
    """Header names and values, with anything credential-shaped removed.

    The key is never printed, not even truncated: a prefix plus a length is
    enough to identify a key in a leak, and this output is meant to be pasted
    into a chat window.
    """
    secret = ("x-goog-api-key", "authorization", "x-goog-user-project",
              "cookie", "set-cookie")
    out = {}
    for k, v in dict(headers).items():
        if k.lower() in secret:
            out[k] = "<redacted, %d chars>" % len(v)
        else:
            out[k] = v
    return out


def _debug_hooks() -> dict:
    """TEMPORARY. httpx event hooks that report what the SDK actually built."""
    def on_request(request):
        _debug("REQUEST  %s %s" % (request.method, request.url))
        _debug("  scheme=%s host=%s path=%s" % (request.url.scheme,
                                                request.url.host,
                                                request.url.path))
        parts = [p for p in request.url.path.split("/") if p]
        _debug("  api_version=%s" % (parts[0] if parts else "<none>"))
        _debug("  headers=%r" % (_redact(request.headers),))
        _debug("  body_bytes=%d" % len(request.content or b""))

    def on_response(response):
        response.read()
        body = response.text
        _debug("RESPONSE %s %s" % (response.status_code, response.reason_phrase))
        _debug("  from=%s" % response.url)
        _debug("  resp_headers=%r" % (_redact(response.headers),))
        _debug("  body=%s" % (body[:1500].replace("\n", " ")))

    return {"request": [on_request], "response": [on_response]}


_PROVIDER_MESSAGE_MAX = 300


def _provider_message(exc: BaseException) -> Optional[str]:
    """The provider's own `error.message`, made safe to show an officer.

    ONLY the parsed `message` field, never `str(exc)` -- this SDK puts the
    entire response body in str(), and a provider error body can echo request
    content. The field can be absent, null, or not even a string, so every one
    of those is checked rather than assumed.

    Collapsed to one line and truncated: this lands in a UI notice, and a
    newline or a kilobyte of text in there is its own small defect.
    """
    raw = getattr(exc, "message", None)
    if not isinstance(raw, str):
        return None
    text = " ".join(raw.split())                  # also drops \r, \n and tabs
    if not text:
        return None
    if len(text) > _PROVIDER_MESSAGE_MAX:
        text = text[:_PROVIDER_MESSAGE_MAX - 1].rstrip() + "\u2026"
    return text


def _debug_exception(exc: BaseException) -> None:
    """TEMPORARY. The full exception identity, not just the mapped message."""
    if not os.environ.get(ENV_DEBUG, "").strip():
        return
    _debug("EXCEPTION %s.%s" % (type(exc).__module__, type(exc).__name__))
    _debug("  mro=%s" % [b.__module__ + "." + b.__name__
                         for b in type(exc).__mro__[:6]])
    _debug("  str=%s" % str(exc)[:1500])
    for attr in ("code", "status", "message"):
        if hasattr(exc, attr):
            _debug("  .%s=%r" % (attr, getattr(exc, attr)))
    cause = exc.__cause__ or exc.__context__
    if cause is not None:
        _debug("  caused-by %s.%s: %s" % (type(cause).__module__,
                                          type(cause).__name__,
                                          str(cause)[:400]))


def _gemini_call(api_key: str, model: str) -> Callable[[bytes, str], str]:
    """The Gemini branch. Same contract as the Anthropic one.

    Identical in every respect that matters: a 30-second hard timeout, no
    retries, the raw response text returned as a string, no JSON parsing here,
    and `lm_extract.VISION_PROMPT` passed through untouched by the caller. Its
    auth, timeout and transport failures are mapped onto the same two
    exceptions so all four failure branches in `/extract-declarations` behave
    the same whichever provider is configured.

    The SDK is imported HERE, not at module scope, so the app starts and every
    test passes with `google-genai` absent.

    This is the current `google-genai` package, not the retired
    `google-generativeai` one. The old package returned 404 for models the key
    demonstrably had -- `gemini-2.5-flash` and `gemini-flash-latest`, both
    listed by the REST models endpoint on the same key. This one puts the
    configured name straight into the request path
    (`/v1beta/models/<name>:generateContent`), so whatever the key can reach,
    the app can reach. Set LM_VISION_MODEL to pick one; DEFAULT_MODELS is
    unchanged.

    Three things worth knowing, none of them a defect:
      * `HttpOptions.timeout` is in MILLISECONDS, unlike every other timeout in
        this codebase. Hence the conversion; do not delete it.
      * `HttpRetryOptions(attempts=1)` is how this SDK is told not to retry --
        attempts counts the original request. Left unset it retries three
        times, which is 90 seconds with an officer standing at the bench.
      * Gemini does not accept image/gif, which `_media_type` returns for a
        GIF. Unreachable from this app: `ALLOWED_IMAGE` in main.py has no
        `.gif`. If GIF uploads are ever allowed, convert it to PNG here the way
        `_media_type` already converts BMP and TIFF.
    """
    try:
        from google import genai
        from google.genai import errors as gerr
        from google.genai import types as gtypes
        import httpx                             # the SDK's sync transport
    except ImportError as exc:                   # pragma: no cover - env dependent
        raise VisionUnavailable(
            "the google-genai SDK is not installed") from exc

    http_options = gtypes.HttpOptions(
        timeout=int(TIMEOUT_SECONDS * 1000),
        retry_options=gtypes.HttpRetryOptions(attempts=1),
    )
    if os.environ.get(ENV_DEBUG, "").strip():
        # TEMPORARY. client_args reaches the SDK's own httpx client, so the
        # timeout and retry settings above still apply exactly as they do
        # without the switch. Nothing about the request changes.
        http_options.client_args = {"event_hooks": _debug_hooks()}
    client = genai.Client(api_key=api_key, http_options=http_options)
    config = gtypes.GenerateContentConfig(
        max_output_tokens=MAX_TOKENS,
        # No tools are passed, so there is nothing for a function-calling loop
        # to call. Disabling it keeps one request one request, and silences a
        # library warning on stderr that would otherwise appear mid-inspection.
        automatic_function_calling=gtypes.AutomaticFunctionCallingConfig(
            disable=True),
    )

    def call(image_bytes: bytes, prompt: str) -> str:
        payload, media = _media_type(image_bytes)
        try:
            resp = client.models.generate_content(
                model=model,
                contents=[gtypes.Part.from_bytes(data=payload, mime_type=media),
                          prompt],
                config=config,
            )
        except httpx.TimeoutException as exc:
            _debug_exception(exc)
            raise VisionTransportError(
                f"the extraction service did not respond within "
                f"{int(TIMEOUT_SECONDS)} seconds") from exc
        except gerr.APIError as exc:
            _debug_exception(exc)
            code = getattr(exc, "code", None)
            if code in (401, 403):
                raise VisionTransportError(
                    "the extraction service rejected the configured "
                    "credentials") from exc
            if code == 429:
                raise VisionTransportError(
                    "the extraction service is rate limiting this key") from exc
            if code == 503:
                raise VisionTransportError(
                    "the extraction service could not be reached") from exc
            if code == 404:
                # The one status that gets to quote the provider. A 404 here is
                # always about the model name, and Google says exactly what is
                # wrong and what to use instead -- "no longer available to new
                # users. Please update your code to use models/...". Swallowing
                # that and printing "returned status 404" sent two debugging
                # sessions looking for an answer the provider had already
                # given. Every other status stays a bare code on purpose.
                said = _provider_message(exc)
                # rstrip so the provider's own full stop does not collide with
                # the one that closes this clause.
                quoted = (" -- it said: " + said.rstrip(" .")) if said else ""
                raise VisionTransportError(
                    "the extraction service does not have model '%s'%s. "
                    "Check LM_VISION_MODEL." % (model, quoted)) from exc
            # Status code only. Provider error bodies can echo request content,
            # and this SDK puts the whole body in str(exc).
            raise VisionTransportError(
                f"the extraction service returned status "
                f"{code if code is not None else 'unknown'}") from exc
        except httpx.TransportError as exc:
            _debug_exception(exc)
            raise VisionTransportError(
                "the extraction service could not be reached") from exc
        except OSError as exc:
            _debug_exception(exc)
            raise VisionTransportError(
                "the extraction service could not be reached") from exc

        feedback = getattr(resp, "prompt_feedback", None)
        if getattr(feedback, "block_reason", None):
            raise VisionTransportError(
                "the extraction service declined to process this image")

        # Assembled from the parts rather than via `resp.text`, which raises
        # when a response carries no usable part. An empty string here is not
        # an error: `parse_vision_json` owns that decision and already raises
        # ExtractionError on an empty response.
        out = []
        stops = set()
        for cand in (getattr(resp, "candidates", None) or []):
            reason = getattr(cand, "finish_reason", None)
            stops.add(str(getattr(reason, "value", reason) or ""))
            content = getattr(cand, "content", None)
            for part in (getattr(content, "parts", None) or []):
                text = getattr(part, "text", "")
                if text:
                    out.append(text)

        # The retired SDK raised for a candidate stopped on safety grounds. This
        # one just returns a candidate with no parts, which would otherwise
        # reach the officer as a bad-photograph message. Same words as before.
        if not out and (stops & _DECLINED_FINISH_REASONS):
            raise VisionTransportError(
                "the extraction service declined to process this image")
        return "".join(out)

    return call


def make_call(provider: str, api_key: str, model: str) -> Callable[[bytes, str], str]:
    """Return `call(image_bytes, prompt) -> raw response text`.

    The returned callable is what `lm_extract.vision_extract` takes. That
    module never learns which provider this is, and never imports one.
    """
    if not api_key:
        raise VisionUnavailable("no API key configured")
    if provider == PROVIDER_GEMINI:
        return _gemini_call(api_key, model)
    if provider != PROVIDER_ANTHROPIC:
        raise VisionUnavailable(f"unsupported provider {provider!r}")

    try:
        import anthropic
    except ImportError as exc:                   # pragma: no cover - env dependent
        raise VisionUnavailable(
            "the anthropic SDK is not installed") from exc

    client = anthropic.Anthropic(
        api_key=api_key,
        base_url=os.environ.get(ENV_BASE_URL, "").strip() or DEFAULT_BASE_URL,
        timeout=TIMEOUT_SECONDS,
        max_retries=0,                           # see module docstring
    )

    def call(image_bytes: bytes, prompt: str) -> str:
        payload, media = _media_type(image_bytes)
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=MAX_TOKENS,
                # Transcription, not reasoning: the prompt asks for verbatim
                # text and for `null` where it cannot be read. Low effort keeps
                # the officer's wait short, and every value is reviewed by a
                # human before it can become a finding.
                output_config={"effort": "low"},
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image",
                         "source": {"type": "base64", "media_type": media,
                                    "data": base64.standard_b64encode(payload).decode()}},
                        {"type": "text", "text": prompt},
                    ],
                }],
            )
        except anthropic.APITimeoutError as exc:
            raise VisionTransportError(
                f"the extraction service did not respond within "
                f"{int(TIMEOUT_SECONDS)} seconds") from exc
        except anthropic.APIConnectionError as exc:
            raise VisionTransportError(
                "the extraction service could not be reached") from exc
        except anthropic.AuthenticationError as exc:
            raise VisionTransportError(
                "the extraction service rejected the configured credentials") from exc
        except anthropic.RateLimitError as exc:
            raise VisionTransportError(
                "the extraction service is rate limiting this key") from exc
        except anthropic.APIStatusError as exc:
            # Status code only. Provider error bodies can echo request content.
            raise VisionTransportError(
                f"the extraction service returned status {exc.status_code}") from exc

        if getattr(resp, "stop_reason", None) == "refusal":
            raise VisionTransportError(
                "the extraction service declined to process this image")
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")

    return call


def call_from_env() -> tuple[Callable[[bytes, str], str], str]:
    """(callable, model) for the configured provider. Raises VisionUnavailable."""
    cfg = configured()
    if cfg is None:
        raise VisionUnavailable("no extraction provider is configured")
    return (make_call(cfg["provider"], os.environ[ENV_KEY].strip(), cfg["model"]),
            cfg["model"])


# --------------------------------------------------------------------------
# Optional local OCR, for the cross-check
# --------------------------------------------------------------------------
def ocr_text(image_bytes: bytes) -> str:
    """A plain OCR dump of the same image, or "" if OCR is unavailable.

    Optional by design. With pytesseract or the tesseract binary absent this
    returns "" and `crosscheck_verbatim` leaves every field
    `verbatim_confirmed=None` -- no cross-check was possible, so nothing is
    marked suspect. Absent evidence is not evidence.
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return ""
    try:
        with Image.open(io.BytesIO(image_bytes)) as im:
            return pytesseract.image_to_string(im.convert("L")) or ""
    except Exception:
        # A missing tesseract binary, an unreadable image, a locale failure:
        # all of them mean "no cross-check was possible", never "suspect".
        return ""
