"""
AzerothCore SOAP client.

AzerothCore's worldserver exposes an HTTP SOAP endpoint (default port 7878)
that accepts GM commands from authenticated accounts.

Required worldserver.conf settings:
    SOAP.Enabled = 1
    SOAP.IP = 127.0.0.1
    SOAP.Port = 7878
"""
from __future__ import annotations

import httpx

_SOAP_ENVELOPE = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope
    xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:ns1="urn:AC">
  <SOAP-ENV:Body>
    <ns1:executeCommand>
      <command>{command}</command>
    </ns1:executeCommand>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

_HEADERS = {
    "Content-Type": "text/xml; charset=utf-8",
    "SOAPAction": "urn:AC#executeCommand",
}


def _parse_response(xml: str) -> str:
    """Extract the result string from a SOAP response body."""
    start = xml.find("<result>")
    end = xml.find("</result>")
    if start != -1 and end != -1:
        return xml[start + 8 : end].strip()
    return xml.strip()


async def execute_command(command: str) -> tuple[bool, str]:
    """
    Send a GM command to the worldserver via SOAP.
    Returns (success, result_text).
    """
    from app.services.panel_settings import get_settings_dict
    s = await get_settings_dict()

    soap_user = s["AC_SOAP_USER"]
    soap_password = s["AC_SOAP_PASSWORD"]

    if not soap_user or not soap_password:
        return False, "SOAP credentials not configured (set AC_SOAP_USER / AC_SOAP_PASSWORD in Settings)"

    url = f"http://{s['AC_SOAP_HOST']}:{s['AC_SOAP_PORT']}/"
    body = _SOAP_ENVELOPE.format(command=command)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url,
                content=body.encode("utf-8"),
                headers=_HEADERS,
                auth=(soap_user, soap_password),
            )
        if resp.status_code == 200:
            return True, _parse_response(resp.text)
        return False, f"SOAP error HTTP {resp.status_code}: {resp.text[:200]}"
    except httpx.ConnectError:
        return False, "Cannot connect to worldserver SOAP endpoint – is the server running?"
    except Exception as exc:
        return False, f"SOAP request failed: {exc}"


# ---------------------------------------------------------------------------
# Convenience wrappers for common commands
# ---------------------------------------------------------------------------

async def get_server_info() -> tuple[bool, str]:
    return await execute_command("server info")


async def get_online_players() -> tuple[bool, str]:
    return await execute_command("account online")


async def kick_player(name: str) -> tuple[bool, str]:
    return await execute_command(f"kick {name}")


async def ban_account(account: str, duration: str, reason: str) -> tuple[bool, str]:
    return await execute_command(f"ban account {account} {duration} {reason}")


async def unban_account(account: str) -> tuple[bool, str]:
    return await execute_command(f"unban account {account}")


async def send_announcement(message: str) -> tuple[bool, str]:
    return await execute_command(f"server announce {message}")


async def send_notify(message: str) -> tuple[bool, str]:
    return await execute_command(f"server notify {message}")


async def whisper_player(player: str, message: str) -> tuple[bool, str]:
    return await execute_command(f"send message {player} {message}")


async def modify_player_level(player: str, level: int) -> tuple[bool, str]:
    return await execute_command(f"character level {player} {level}")


async def add_item(player: str, item_id: int, count: int = 1) -> tuple[bool, str]:
    return await execute_command(f"send items {player} 'Panel gift' 'Sent via AzerothPanel' {item_id}:{count}")


async def add_money(player: str, copper: int) -> tuple[bool, str]:
    return await execute_command(f"send money {player} 'Panel gift' 'Sent via AzerothPanel' {copper}")

