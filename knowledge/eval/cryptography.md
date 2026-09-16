# Applied Cryptography

## Symmetric ciphers

Symmetric encryption uses one secret key for both encryption and decryption. AES with
128 or 256 bit keys is the standard choice for data at rest because hardware
instructions make it extremely fast. AES runs in block cipher modes, and the mode
matters as much as the cipher: CBC requires random initialisation vectors and pads the
plaintext, while GCM provides authentication in the same pass and rejects tampered
ciphertext. Never use ECB, which leaks identical plaintext blocks as identical
ciphertext blocks.

## Asymmetric cryptography

Public key systems pair a secret with a widely published key. RSA is still common but
uses large key sizes, typically 2048 bits or more, and cannot encrypt data larger than
the key modulus. Elliptic curve cryptography, most commonly ECDSA and ECDH on the
P-256 curve, achieves comparable security with much shorter keys. Asymmetric cryptosystems
are orders of magnitude slower than symmetric ones, so protocols use them only to agree
on a session key or sign a digest, never to encrypt the bulk of the payload.

## Hash functions

A cryptographic hash is a one-way, collision-resistant fingerprint of arbitrary input.
SHA-256 produces a fixed 256 bit digest and is the default for file integrity and
software distribution. Message digests must be treated as raw bytes rather than human
readable strings when used for comparison, to avoid encoding confusion. Password
storage should never use a raw fast hash; instead a key derivation function such as
PBKDF2 with a per-user random salt and hundreds of thousands of iterations slows down
brute force attacks.

## Key exchange

Diffie-Hellman key exchange lets two parties agree on a shared secret over an
untrusted channel. The classic algorithm is vulnerable to man-in-the-middle attacks
because neither side knows whom it is talking to, so real deployments wrap it in a
certificate-authenticated handshake such as TLS. Ephemeral Diffie-Hellman variants
generate a fresh key per session, providing forward secrecy: stealing the long term
private key later cannot decrypt old recorded traffic.

## Authentication and integrity

Digital signatures combine a hash with asymmetric encryption. The signer produces a
digest of the message and encrypts that digest with their private key; anyone with the
public key can decrypt it and confirm the message has not been altered. Message
authentication codes such as HMAC-SHA256 provide the same tamper detection with a
shared secret and are cheaper when both parties already share a key. The practical
rule is to prefer authenticated encryption or signatures rather than inventing layered
constructions.

## Padding and side channels

Block ciphers need the plaintext padded to a multiple of the block size. PKCS7 adds a
full block of padding bytes when the message already fills the last block, and any
padding scheme must be checked in constant time. Padding oracles were exploited for
years because applications revealed whether decrypted padding was valid, letting an
attacker peel the ciphertext one byte at a time. Compare MACs with a constant time
comparison function as well, because a normal equality check leaks information through
timing about how many leading bytes matched.

## Randomness and key hygiene

Cryptographic security begins with honest randomness. Keys and salts must come from a
Cryptographically Secure PRNG, never from a language default that might reuse state or
seed predictably. Once a key is rotated or retired it should be irrevocably destroyed,
and disk images should be scrubbed before disposal. Key material belongs in a hardware
security module or a dedicated keystore with access control, not in a configuration
file committed to source control. The era of "encrypt it and never rotate" is over;
modern designs assume a component will be compromised and build periodic rotation into
the system from day one.