import hashlib
from auth.auth import authenticate, load_users, DEFAULT_USERS_FILE, PBKDF2_ITERATIONS


def test_default_users_exist_and_roles_are_registered():
    users = load_users()
    assert "arturo" in users
    assert "administrador" in users
    assert users["arturo"].role == "user"
    assert users["administrador"].role == "administrator"


def test_default_registry_does_not_store_password_as_plaintext():
    registry = DEFAULT_USERS_FILE.read_text(encoding="utf-8")
    assert registry.count("|") >= 6
    for line in registry.splitlines():
        if line and not line.startswith("#"):
            assert len(line.split("|")) == 4


def test_authentication_uses_hashes_and_username_is_case_insensitive(tmp_path):
    password = "unit-test-secret"
    salt = bytes.fromhex("00112233445566778899aabbccddeeff")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    registry = tmp_path / "users.txt"
    registry.write_text(f"Example|user|{salt.hex()}|{digest.hex()}\n", encoding="utf-8")
    assert authenticate("EXAMPLE", password, registry) is not None
    assert authenticate("Example", "incorrect", registry) is None
