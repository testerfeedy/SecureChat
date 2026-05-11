"""
End-to-End Encryption для SecureChat

Схема:
  1. При старте клиент генерирует RSA-2048 пару ключей
  2. Публичный ключ загружается на сервер
  3. Для каждого DM:
     - Генерируется случайный AES-256 ключ
     - AES ключ шифруется RSA публичным ключом получателя
     - Сообщение шифруется AES-256-GCM
  4. Расшифровка: AES ключ → RSA приватный ключ → AES → сообщение
"""

import base64
import json
import os
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend


class E2EEncryption:
    """End-to-End шифрование RSA-2048 + AES-256-GCM"""

    def __init__(self):
        self._private_key = None
        self._public_key = None

    def generate_keypair(self) -> tuple[str, str]:
        """Генерировать пару RSA-2048 ключей. Возвращает (private_pem, public_pem)"""
        self._private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        self._public_key = self._private_key.public_key()
        return self.get_private_pem(), self.get_public_pem()

    def load_private_key(self, private_pem: str):
        """Загрузить приватный ключ из PEM"""
        self._private_key = serialization.load_pem_private_key(
            private_pem.encode(),
            password=None,
            backend=default_backend()
        )
        self._public_key = self._private_key.public_key()

    def get_private_pem(self) -> str:
        if not self._private_key:
            raise ValueError("No private key loaded")
        return self._private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode()

    def get_public_pem(self) -> str:
        if not self._public_key:
            raise ValueError("No public key loaded")
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()

    def encrypt_message(self, plaintext: str, recipient_public_pem: str) -> str:
        """
        Шифровать сообщение для получателя.
        Возвращает base64-encoded JSON blob.
        """
        # 1. Генерируем разовый AES-256 ключ
        aes_key = os.urandom(32)

        # 2. Шифруем сообщение AES-256-GCM
        aesgcm = AESGCM(aes_key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

        # 3. Шифруем AES ключ публичным RSA ключом получателя
        recipient_pub = serialization.load_pem_public_key(
            recipient_public_pem.encode(),
            backend=default_backend()
        )
        encrypted_aes_key = recipient_pub.encrypt(
            aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        blob = {
            "v": 1,
            "enc_key": base64.b64encode(encrypted_aes_key).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "ciphertext": base64.b64encode(ciphertext).decode(),
        }
        return base64.b64encode(json.dumps(blob).encode()).decode()

    def decrypt_message(self, encrypted_blob: str) -> str:
        """
        Расшифровать сообщение своим приватным ключом.
        """
        if not self._private_key:
            raise ValueError("No private key loaded")

        blob = json.loads(base64.b64decode(encrypted_blob).decode())
        if blob.get("v") != 1:
            raise ValueError("Unknown encryption version")

        # 1. Расшифровываем AES ключ своим RSA приватным ключом
        encrypted_aes_key = base64.b64decode(blob["enc_key"])
        aes_key = self._private_key.decrypt(
            encrypted_aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        # 2. Расшифровываем сообщение AES-256-GCM
        nonce = base64.b64decode(blob["nonce"])
        ciphertext = base64.b64decode(blob["ciphertext"])
        aesgcm = AESGCM(aes_key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")

    def save_private_key(self, filepath: str, passphrase: bytes = None):
        """Сохранить приватный ключ в файл (опционально с паролем)"""
        encryption = (
            serialization.BestAvailableEncryption(passphrase)
            if passphrase
            else serialization.NoEncryption()
        )
        pem = self._private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=encryption
        )
        with open(filepath, "wb") as f:
            f.write(pem)

    def load_private_key_file(self, filepath: str, passphrase: bytes = None):
        """Загрузить приватный ключ из файла"""
        with open(filepath, "rb") as f:
            self._private_key = serialization.load_pem_private_key(
                f.read(),
                password=passphrase,
                backend=default_backend()
            )
        self._public_key = self._private_key.public_key()
