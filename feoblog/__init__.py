import requests
from base58 import b58decode, b58encode, b58decode_check
from nacl.signing import SigningKey

from . import protos

   
class UserID:
    def __init__(self, as_string: str, as_bytes: bytes):
        self.string = as_string
        self.bytes = as_bytes

    def __str__(self):
        return self.string


    @staticmethod
    def from_string(value: str) -> "UserID":
        binary = b58decode(value)
        # TODO: Verify correct number of bytes.

        return UserID(as_string=value, as_bytes=binary)

class Signature:
    def __init__(self, as_string: str, as_bytes: bytes):
        self.string = as_string
        self.bytes = as_bytes

    @staticmethod
    def from_string(value: str) -> "Signature":
        binary = b58decode(value)
        # TODO: Verify correct number of bytes.

        return Signature(as_string=value, as_bytes=binary)

    @staticmethod 
    def from_bytes(value: bytes) -> "Signature":
        # TODO validate byte length.
        return Signature(
            as_string=b58encode(value).decode("ascii"),
            as_bytes=value
        )

    def __str__(self):
        return self.string

class Password:
    def __init__(self, as_string: str, as_bytes: bytes):
        self.string = as_string
        self.bytes = as_bytes
        self._sign_key = SigningKey(self.bytes)


    @staticmethod
    def from_string(value: str) -> "Password":
        binary = b58decode_check(value)
        # TODO: Verify correct number of bytes.

        return Password(as_string=value, as_bytes=binary)

    def matches_user(self, user_id: UserID) -> bool:
        return bytes(self._sign_key.verify_key) == user_id.bytes

    def sign(self, data: bytes) -> Signature:
        signed_message = self._sign_key.sign(data)
        sig_bytes = signed_message.signature
        return Signature.from_bytes(sig_bytes)



class Client:
    def __init__(self, base_url):
        self._base_url = base_url
    
    def get_user_items(self, user_id: UserID):
        url = self._base_url + f"/u/{user_id.string}/proto3"

        response = requests.get(url)
        items = protos.ItemList()
        items.ParseFromString(response.content)
        for entry in items.items:
            yield entry

        # TODO: implement pagination. Not needed for this case, though.
        

    def put_item(self, user_id: UserID, signature: Signature, item_bytes: bytes):
        url = f"{self._base_url}/u/{user_id}/i/{signature}/proto3"        
        response = requests.put(url, item_bytes)
        response.raise_for_status()
