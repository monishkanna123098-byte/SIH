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

PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_GEMINI = "gemini"
PROVIDERS = (PROVIDER_ANTHROPIC, PROVIDER_GEMINI)

DEFAULT_MODELS = {
    PROVIDER_ANTHROPIC: "claude-opus-5",
    PROVIDER_GEMINI: "gemini-2.0-flash",
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


def _gemini_call(api_key: str, model: str) -> Callable[[bytes, str], str]:
    """The Gemini branch. Same contract as the Anthropic one.

    Identical in every respect that matters: a 30-second hard timeout, no
    retries, the raw response text returned as a string, no JSON parsing here,
    and `lm_extract.VISION_PROMPT` passed through untouched by the caller. Its
    auth, timeout and transport failures are mapped onto the same two
    exceptions so all four failure branches in `/extract-declarations` behave
    the same whichever provider is configured.

    The SDK is imported HERE, not at module scope, so the app starts and every
    test passes with `google-generativeai` absent.

    Two things worth knowing, neither of them a defect:
      * `genai.configure()` is process-global. This app configures one provider
        once from the environment, so that is acceptable -- but a second
        provider in the same process would clobber it.
      * Gemini does not accept image/gif, which `_media_type` returns for a
        GIF. Unreachable from this app: `ALLOWED_IMAGE` in main.py has no
        `.gif`. If GIF uploads are ever allowed, convert it to PNG here the way
        `_media_type` already converts BMP and TIFF.
    """
    try:
        import google.generativeai as genai
        from google.generativeai import types as gtypes
        from google.api_core import exceptions as gexc
    except ImportError as exc:                   # pragma: no cover - env dependent
        raise VisionUnavailable(
            "the google-generativeai SDK is not installed") from exc

    genai.configure(api_key=api_key)
    client = genai.GenerativeModel(model_name=model)

    def call(image_bytes: bytes, prompt: str) -> str:
        payload, media = _media_type(image_bytes)
        try:
            resp = client.generate_content(
                [{"mime_type": media, "data": payload}, prompt],
                # retry=None is how this SDK is told not to retry. A retry
                # doubles the wait with an officer standing at the bench.
                request_options=gtypes.RequestOptions(
                    timeout=TIMEOUT_SECONDS, retry=None),
            )
        except gexc.DeadlineExceeded as exc:
            raise VisionTransportError(
                f"the extraction service did not respond within "
                f"{int(TIMEOUT_SECONDS)} seconds") from exc
        except gexc.RetryError as exc:
            raise VisionTransportError(
                f"the extraction service did not respond within "
                f"{int(TIMEOUT_SECONDS)} seconds") from exc
        except (gexc.Unauthenticated, gexc.PermissionDenied) as exc:
            raise VisionTransportError(
                "the extraction service rejected the configured credentials") from exc
        except gexc.ResourceExhausted as exc:
            raise VisionTransportError(
                "the extraction service is rate limiting this key") from exc
        except gexc.ServiceUnavailable as exc:
            raise VisionTransportError(
                "the extraction service could not be reached") from exc
        except gexc.GoogleAPICallError as exc:
            # Status code only. Provider error bodies can echo request content.
            raise VisionTransportError(
                f"the extraction service returned status "
                f"{getattr(exc, 'code', 'unknown')}") from exc
        except (gtypes.BlockedPromptException,
                gtypes.StopCandidateException) as exc:
            raise VisionTransportError(
                "the extraction service declined to process this image") from exc
        except OSError as exc:
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
        for cand in (getattr(resp, "candidates", None) or []):
            content = getattr(cand, "content", None)
            for part in (getattr(content, "parts", None) or []):
                text = getattr(part, "text", "")
                if text:
                    out.append(text)
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
