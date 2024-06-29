
from keyring.backend import KeyringBackend

def get_password(service_name: str, username: str) -> str | None: ...
def set_password(service_name: str, username: str, password: str) -> None: ...
def delete_password(service_name: str, username: str) -> None: ...
def recommended(backend: KeyringBackend) -> bool: ...
def get_keyring() -> KeyringBackend: ...
