"""Adapter: browser TTS speech output (placeholder for JS bridge).

In a full web deployment this would push messages to the browser
via WebSocket to use the Web Speech API.  Here it logs the call.
"""

from __future__ import annotations

import logging

from pitwall.domain.models import RadioCall
from pitwall.ports.speech import SpeechOutput

logger = logging.getLogger(__name__)


class BrowserTTSSpeechOutput(SpeechOutput):
    """Speech adapter that would bridge to the browser Web Speech API.

    Currently logs the radio call; a real implementation would push
    the message over a WebSocket to the browser client.
    """

    async def speak(self, call: RadioCall) -> None:
        """Log the radio call for browser TTS delivery."""
        logger.info(
            "🔊 [TTS] %s (priority=%s, cid=%s)",
            call.message,
            call.priority.value,
            str(call.correlation_id)[:8],
        )
