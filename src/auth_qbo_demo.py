# src/auth_qbo_demo.py
"""
Demo authentication layer for QuickBooks Online.

In production this would implement an OAuth 2.0 flow and return an
authorized HTTP session plus the QBO realm id. For this demo it just
returns a simple placeholder object and a fake realm id so that the
rest of the code can be wired without hitting real APIs.
"""

from dataclasses import dataclass


@dataclass
class FakeQboSession:
    """
    Minimal stand-in for a real HTTP session.

    It is deliberately small. The uploader in this demo does not call
    it directly because the attachment calls go through fake_qbo_api.
    The session exists here purely to mirror the real project structure.
    """
    name: str = "fake-qbo-session"


def get_qbo_session():
    """
    Return a fake QBO "session" and a fake realm id.

    A real implementation would:
      - load client id / secret and refresh token
      - refresh or obtain an access token
      - build a requests.Session with Authorization headers
      - look up or store the realm id

    The uploader can treat this as a black box that
    returns (session_like_object, realm_id).
    """
    session = FakeQboSession()
    realm_id = "1234567890"  # dummy realm id for demo purposes
    return session, realm_id
