(() => {
    'use strict';

    const encoder = new TextEncoder();
    const decoder = new TextDecoder();
    const iterations = 600000;
    const keySize = 256;
    const nonceSize = 12;

    function encodeBase64(bytes) {
        let binary = '';
        for (const byte of bytes) {
            binary += String.fromCharCode(byte);
        }
        return btoa(binary)
            .replaceAll('+', '-')
            .replaceAll('/', '_')
            .replace(/=+$/, '');
    }

    function decodeBase64(value) {
        const base64 = value.replaceAll('-', '+').replaceAll('_', '/');
        const binary = atob(base64 + '='.repeat((4 - base64.length % 4) % 4));
        return Uint8Array.from(binary, (character) => character.charCodeAt(0));
    }

    function toBytes(value) {
        if (typeof value === 'string') {
            return encoder.encode(value);
        }
        if (value instanceof ArrayBuffer) {
            return new Uint8Array(value);
        }
        return new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
    }

    function publicKeyBytes(publicKey) {
        if (typeof publicKey !== 'string') {
            return publicKey;
        }
        const encoded = publicKey.includes('-----BEGIN')
            ? publicKey.replace(/-----[^-]+-----/g, '').replace(/\s/g, '')
            : publicKey;
        return decodeBase64(encoded);
    }

    async function importPublicKey(publicKey) {
        if (publicKey instanceof CryptoKey) {
            if (
                publicKey.type !== 'public'
                || publicKey.algorithm.name !== 'RSA-OAEP'
                || publicKey.algorithm.modulusLength !== 3072
                || publicKey.algorithm.hash.name !== 'SHA-256'
            ) {
                throw new Error('The public key must be RSA-3072.');
            }
            return publicKey;
        }
        if (publicKey && typeof publicKey === 'object') {
            const importedKey = await importPublicKey(publicKey.public_key);
            if (
                publicKey.fingerprint
                && publicKey.fingerprint !== await fingerprintPublicKey(importedKey)
            ) {
                throw new Error('The public key fingerprint does not match.');
            }
            return importedKey;
        }
        const key = await crypto.subtle.importKey(
            'spki',
            publicKeyBytes(publicKey),
            { name: 'RSA-OAEP', hash: 'SHA-256' },
            true,
            ['encrypt', 'wrapKey'],
        );
        if (
            key.algorithm.name !== 'RSA-OAEP'
            || key.algorithm.modulusLength !== 3072
            || key.algorithm.hash.name !== 'SHA-256'
        ) {
            throw new Error('The public key must be RSA-3072.');
        }
        return key;
    }

    async function fingerprintPublicKey(publicKey) {
        const key = await importPublicKey(publicKey);
        const digest = await crypto.subtle.digest(
            'SHA-256',
            await crypto.subtle.exportKey('spki', key),
        );
        return Array.from(new Uint8Array(digest), (byte) =>
            byte.toString(16).padStart(2, '0'),
        ).join('');
    }

    async function generateDataKey() {
        return crypto.subtle.generateKey(
            { name: 'AES-GCM', length: keySize },
            true,
            ['encrypt', 'decrypt', 'wrapKey', 'unwrapKey'],
        );
    }

    async function encryptBytes(data, key) {
        const nonce = crypto.getRandomValues(new Uint8Array(nonceSize));
        const ciphertext = await crypto.subtle.encrypt(
            { name: 'AES-GCM', iv: nonce },
            key,
            toBytes(data),
        );
        return {
            ciphertext: encodeBase64(new Uint8Array(ciphertext)),
            nonce: encodeBase64(nonce),
        };
    }

    async function decryptBytes(ciphertext, nonce, key) {
        const plaintext = await crypto.subtle.decrypt(
            { name: 'AES-GCM', iv: decodeBase64(nonce) },
            key,
            decodeBase64(ciphertext),
        );
        return new Uint8Array(plaintext);
    }

    async function wrapDataKey(dataKey, publicKey) {
        const key = await importPublicKey(publicKey);
        const wrapped = await crypto.subtle.wrapKey('raw', dataKey, key, {
            name: 'RSA-OAEP',
        });
        return {
            fingerprint: await fingerprintPublicKey(key),
            ciphertext: encodeBase64(new Uint8Array(wrapped)),
        };
    }

    async function unwrapDataKey(wrappedKey, privateKey) {
        return crypto.subtle.unwrapKey(
            'raw',
            decodeBase64(wrappedKey.ciphertext),
            privateKey,
            { name: 'RSA-OAEP' },
            { name: 'AES-GCM', length: keySize },
            true,
            ['encrypt', 'decrypt'],
        );
    }

    async function passwordKey(password, salt) {
        const material = await crypto.subtle.importKey(
            'raw',
            encoder.encode(password),
            'PBKDF2',
            false,
            ['deriveKey'],
        );
        return crypto.subtle.deriveKey(
            { name: 'PBKDF2', hash: 'SHA-256', salt, iterations },
            material,
            { name: 'AES-GCM', length: keySize },
            false,
            ['encrypt', 'decrypt'],
        );
    }

    async function wrapDataKeyWithPassword(dataKey, password, side) {
        const salt = crypto.getRandomValues(new Uint8Array(16));
        const nonce = crypto.getRandomValues(new Uint8Array(nonceSize));
        const key = await passwordKey(password, salt);
        const rawKey = await crypto.subtle.exportKey('raw', dataKey);
        const ciphertext = await crypto.subtle.encrypt(
            { name: 'AES-GCM', iv: nonce },
            key,
            rawKey,
        );
        return {
            side,
            ciphertext: encodeBase64(new Uint8Array(ciphertext)),
            salt: encodeBase64(salt),
            nonce: encodeBase64(nonce),
        };
    }

    async function unwrapDataKeyWithPassword(wrappedKey, password) {
        const key = await passwordKey(
            password,
            decodeBase64(wrappedKey.salt),
        );
        const rawKey = await crypto.subtle.decrypt(
            { name: 'AES-GCM', iv: decodeBase64(wrappedKey.nonce) },
            key,
            decodeBase64(wrappedKey.ciphertext),
        );
        return crypto.subtle.importKey(
            'raw',
            rawKey,
            { name: 'AES-GCM', length: keySize },
            true,
            ['encrypt', 'decrypt'],
        );
    }

    async function encryptEnvelope(plaintext, publicKeys, temporaryPasswords = []) {
        const dataKey = await generateDataKey();
        const encrypted = await encryptBytes(plaintext, dataKey);
        const wrappedKeys = await Promise.all(
            publicKeys.map((publicKey) => wrapDataKey(dataKey, publicKey)),
        );
        const temporaryWrappedKeys = await Promise.all(
            temporaryPasswords.map(({ side, password }) =>
                wrapDataKeyWithPassword(dataKey, password, side),
            ),
        );
        return {
            ...encrypted,
            wrapped_keys: wrappedKeys,
            temporary_wrapped_keys: temporaryWrappedKeys,
        };
    }

    async function encryptMessage(
        plaintext,
        attachments,
        publicKeys,
        temporaryPasswords = [],
    ) {
        const dataKey = await generateDataKey();
        const [body, encryptedAttachments] = await Promise.all([
            encryptEnvelopeWithKey(
                plaintext,
                dataKey,
                publicKeys,
                temporaryPasswords,
            ),
            Promise.all(
                attachments.map((file) => encryptAttachment(file, dataKey)),
            ),
        ]);
        return { envelope: body, attachments: encryptedAttachments };
    }

    async function encryptEnvelopeWithKey(
        plaintext,
        dataKey,
        publicKeys,
        temporaryPasswords,
    ) {
        const encrypted = await encryptBytes(plaintext, dataKey);
        const wrappedKeys = await Promise.all(
            publicKeys.map((publicKey) => wrapDataKey(dataKey, publicKey)),
        );
        const temporaryWrappedKeys = await Promise.all(
            temporaryPasswords.map(({ side, password }) =>
                wrapDataKeyWithPassword(dataKey, password, side),
            ),
        );
        return {
            ...encrypted,
            wrapped_keys: wrappedKeys,
            temporary_wrapped_keys: temporaryWrappedKeys,
        };
    }

    async function decryptEnvelope(
        envelope,
        { privateKey, fingerprint, temporaryPassword, side },
    ) {
        let dataKey;
        if (temporaryPassword !== undefined) {
            const wrappedKey = envelope.temporary_wrapped_keys.find(
                (key) => key.side === side,
            );
            if (!wrappedKey) {
                throw new Error(`No temporary key for the ${side} side.`);
            }
            dataKey = await unwrapDataKeyWithPassword(
                wrappedKey,
                temporaryPassword,
            );
        } else {
            const wrappedKey = envelope.wrapped_keys.find(
                (key) => key.fingerprint === fingerprint,
            );
            if (!wrappedKey) {
                throw new Error('This message is unavailable on this device.');
            }
            dataKey = await unwrapDataKey(wrappedKey, privateKey);
        }
        return decoder.decode(
            await decryptBytes(envelope.ciphertext, envelope.nonce, dataKey),
        );
    }

    async function encryptAttachment(file, dataKey) {
        const [encryptedFile, encryptedFilename] = await Promise.all([
            encryptBytes(await file.arrayBuffer(), dataKey),
            encryptBytes(file.name, dataKey),
        ]);
        return {
            ciphertext: encryptedFile.ciphertext,
            metadata: {
                encrypted_filename: encryptedFilename.ciphertext,
                filename_nonce: encryptedFilename.nonce,
                nonce: encryptedFile.nonce,
                content_type: file.type,
                size: decodeBase64(encryptedFile.ciphertext).byteLength,
            },
        };
    }

    async function decryptAttachment(ciphertext, metadata, dataKey) {
        const [contents, filename] = await Promise.all([
            decryptBytes(ciphertext, metadata.nonce, dataKey),
            decryptBytes(
                metadata.encrypted_filename,
                metadata.filename_nonce,
                dataKey,
            ),
        ]);
        return new File([contents], decoder.decode(filename), {
            type: metadata.content_type,
        });
    }

    async function generateDeviceKeyPair() {
        return crypto.subtle.generateKey(
            {
                name: 'RSA-OAEP',
                modulusLength: 3072,
                publicExponent: new Uint8Array([1, 0, 1]),
                hash: 'SHA-256',
            },
            false,
            ['encrypt', 'decrypt', 'wrapKey', 'unwrapKey'],
        );
    }

    async function exportPublicKey(publicKey) {
        return encodeBase64(
            new Uint8Array(await crypto.subtle.exportKey('spki', publicKey)),
        );
    }

    window.E2EE = Object.freeze({
        keys: Object.freeze({
            generateDeviceKeyPair,
            exportPublicKey,
            importPublicKey,
            fingerprintPublicKey,
            getDeviceKey: async () => null,
        }),
        messages: Object.freeze({
            generateDataKey,
            encryptBytes,
            decryptBytes,
            wrapDataKey,
            unwrapDataKey,
            wrapDataKeyWithPassword,
            unwrapDataKeyWithPassword,
            encryptEnvelope,
            encryptMessage,
            decryptEnvelope,
            encryptAttachment,
            decryptAttachment,
        }),
    });
})();
