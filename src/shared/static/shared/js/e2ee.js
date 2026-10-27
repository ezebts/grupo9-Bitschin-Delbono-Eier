(() => {
    'use strict';

    const encoder = new TextEncoder();
    const decoder = new TextDecoder();
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

    async function encryptShared(parts, publicKeys) {
        const dataKey = await generateDataKey();
        const encrypted = {};
        for (const [name, value] of Object.entries(parts)) {
            encrypted[name] = await encryptBytes(value, dataKey);
        }
        const wrappedKeys = await Promise.all(
            publicKeys.map((publicKey) => wrapDataKey(dataKey, publicKey)),
        );
        return { encrypted, wrapped_keys: wrappedKeys };
    }

    async function encryptEnvelope(plaintext, publicKeys) {
        const dataKey = await generateDataKey();
        return encryptEnvelopeWithKey(plaintext, dataKey, publicKeys);
    }

    async function encryptMessage(plaintext, attachments, publicKeys) {
        const dataKey = await generateDataKey();
        const [body, encryptedAttachments] = await Promise.all([
            encryptEnvelopeWithKey(plaintext, dataKey, publicKeys),
            Promise.all(
                attachments.map((file) => encryptAttachment(file, dataKey)),
            ),
        ]);
        return { envelope: body, attachments: encryptedAttachments };
    }

    async function encryptEnvelopeWithKey(plaintext, dataKey, publicKeys) {
        const encrypted = await encryptBytes(plaintext, dataKey);
        const wrappedKeys = await Promise.all(
            publicKeys.map((publicKey) => wrapDataKey(dataKey, publicKey)),
        );
        return { ...encrypted, wrapped_keys: wrappedKeys };
    }

    async function decryptEnvelope(envelope, { privateKey, fingerprint }) {
        const wrappedKey = envelope.wrapped_keys.find(
            (key) => key.fingerprint === fingerprint,
        );
        if (!wrappedKey) {
            throw new Error('This message is unavailable on this device.');
        }
        const dataKey = await unwrapDataKey(wrappedKey, privateKey);
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

    function openDeviceKeyStore(mode) {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open('magistral-e2ee', 1);
            request.onupgradeneeded = () => {
                request.result.createObjectStore('device-keys', {
                    keyPath: 'fingerprint',
                });
            };
            request.onerror = () => reject(request.error);
            request.onsuccess = () => {
                resolve(
                    request.result
                        .transaction('device-keys', mode)
                        .objectStore('device-keys'),
                );
            };
        });
    }

    function storeRequest(request) {
        return new Promise((resolve, reject) => {
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    async function createDeviceKey() {
        const pair = await generateDeviceKeyPair();
        const publicKey = await exportPublicKey(pair.publicKey);
        const deviceKey = {
            fingerprint: await fingerprintPublicKey(publicKey),
            publicKey,
            privateKey: pair.privateKey,
        };
        const store = await openDeviceKeyStore('readwrite');
        await storeRequest(store.put(deviceKey));
        return deviceKey;
    }

    async function getDeviceKey(fingerprints) {
        const store = await openDeviceKeyStore('readonly');
        const deviceKeys = await storeRequest(store.getAll());
        return (
            deviceKeys.find((deviceKey) =>
                fingerprints.includes(deviceKey.fingerprint),
            ) ?? null
        );
    }

    async function ensureDeviceKey(account) {
        const deviceKey = await getDeviceKey(account.fingerprints);
        if (deviceKey) {
            return deviceKey;
        }
        const created = await createDeviceKey();
        await htmx.ajax('POST', account.register_device_url, {
            values: { public_key: created.publicKey },
            swap: 'none',
        });
        return created;
    }

    function accountData() {
        const account = document.getElementById('e2ee-account');
        return account ? JSON.parse(account.textContent) : null;
    }

    async function openEnvelopes(root) {
        const account = accountData();
        if (!account) {
            return;
        }
        const deviceKey = await getDeviceKey(account.fingerprints);
        if (!deviceKey) {
            return;
        }
        const nodes = root.querySelectorAll('[data-e2ee-envelope]');
        await Promise.all(
            [...nodes].map(async (node) => {
                try {
                    node.textContent = await decryptEnvelope(
                        JSON.parse(node.dataset.e2eeEnvelope),
                        deviceKey,
                    );
                } catch {
                    node.textContent = 'Mensaje cifrado';
                }
            }),
        );
    }

    async function openPrescription(node, deviceKey) {
        const sealNode = node.querySelector('script[type="application/json"]');
        if (!sealNode) {
            return;
        }
        const seal = JSON.parse(sealNode.textContent);
        const dataKey = await unwrapDataKey(
            seal.wrapped_keys.find(
                (key) => key.fingerprint === deviceKey.fingerprint,
            ),
            deviceKey.privateKey,
        );
        const filename = decoder.decode(
            await decryptBytes(
                seal.encrypted_filename,
                seal.filename_nonce,
                dataKey,
            ),
        );
        node.querySelectorAll('[data-e2ee-filename]').forEach((item) => {
            item.textContent = filename;
            item.title = filename;
        });
        const response = await fetch(node.dataset.e2eeFile, {
            credentials: 'same-origin',
        });
        const plain = await decryptBytes(
            encodeBase64(new Uint8Array(await response.arrayBuffer())),
            seal.nonce,
            dataKey,
        );
        const blob = new Blob([plain], {
            type: seal.content_type || 'application/octet-stream',
        });
        const url = URL.createObjectURL(blob);
        node.querySelectorAll('[data-e2ee-open], [data-e2ee-download]').forEach(
            (link) => {
                if (link === node) {
                    return;
                }
                link.href = url;
            },
        );
        if (node.matches('[data-e2ee-open], [data-e2ee-download]')) {
            node.href = url;
        }
        node.querySelectorAll('[data-e2ee-download]').forEach((link) => {
            link.download = filename;
        });
        const frame = node.querySelector('[data-e2ee-frame]');
        if (!frame) {
            return;
        }
        if ((seal.content_type || '').startsWith('image/')) {
            const image = document.createElement('img');
            image.src = url;
            image.alt = '';
            image.className = 'prescription-preview__image';
            frame.replaceChildren(image);
            return;
        }
        const iframe = document.createElement('iframe');
        iframe.src = url;
        iframe.className = 'prescription-preview__iframe';
        iframe.title = '';
        frame.replaceChildren(iframe);
    }

    async function openPrescriptions(root) {
        const account = accountData();
        if (!account) {
            return;
        }
        const deviceKey = await getDeviceKey(account.fingerprints);
        if (!deviceKey) {
            return;
        }
        const nodes = root.querySelectorAll('[data-e2ee-prescription]');
        await Promise.all(
            [...nodes].map((node) => openPrescription(node, deviceKey).catch(() => {})),
        );
    }

    async function openSealedContent(root) {
        await openEnvelopes(root);
        await openPrescriptions(root);
    }

    async function sealChatForm(form) {
        const field = form.querySelector('textarea');
        const plaintext = field.value;
        if (plaintext.length > 2000 || field.dataset.sealed === '1') {
            return;
        }
        const keysNode = form.querySelector('#recipient-keys');
        if (!keysNode) {
            return;
        }
        const recipientKeys = JSON.parse(keysNode.textContent).map(
            (key) => key.public_key,
        );
        const account = accountData();
        if (account) {
            const deviceKey = await ensureDeviceKey(account);
            if (!recipientKeys.includes(deviceKey.publicKey)) {
                recipientKeys.push(deviceKey.publicKey);
            }
        }
        if (!recipientKeys.length) {
            return;
        }
        const envelope = await encryptEnvelope(plaintext, recipientKeys);
        field.removeAttribute('maxlength');
        field.value = JSON.stringify(envelope);
        field.dataset.sealed = '1';
    }

    const prescriptionExtensions = ['pdf', 'jpg', 'jpeg', 'png'];
    const prescriptionMaxBytes = 10 * 1024 * 1024;

    function prescriptionError(file) {
        const extension = file.name.split('.').pop().toLowerCase();
        if (!prescriptionExtensions.includes(extension)) {
            return 'La receta tiene que ser un PDF, JPG o PNG.';
        }
        if (file.size > prescriptionMaxBytes) {
            return 'La receta puede pesar hasta 10 MB.';
        }
        return '';
    }

    async function recipientKeysFrom(node) {
        const keysNode = node.querySelector('#order-recipient-keys, #recipient-keys');
        const keys = keysNode
            ? JSON.parse(keysNode.textContent).map((key) => key.public_key)
            : [];
        const account = accountData();
        if (!account) {
            return keys;
        }
        const deviceKey = await ensureDeviceKey(account);
        if (!keys.includes(deviceKey.publicKey)) {
            keys.push(deviceKey.publicKey);
        }
        return keys;
    }

    async function sealPrescriptionForm(form) {
        const input = form.querySelector('input[type=file]');
        const file = input.files[0];
        const error = prescriptionError(file);
        if (error) {
            input.setCustomValidity(error);
            input.reportValidity();
            return;
        }
        input.setCustomValidity('');
        const sealed = await encryptShared(
            {
                filename: file.name,
                file: await file.arrayBuffer(),
            },
            await recipientKeysFrom(form),
        );
        const bytes = decodeBase64(sealed.encrypted.file.ciphertext);
        const transfer = new DataTransfer();
        transfer.items.add(new File([bytes], 'prescription.bin'));
        input.files = transfer.files;
        const seal = document.createElement('input');
        seal.type = 'hidden';
        seal.name = 'prescription_seal';
        seal.value = JSON.stringify({
            encrypted_filename: sealed.encrypted.filename.ciphertext,
            filename_nonce: sealed.encrypted.filename.nonce,
            nonce: sealed.encrypted.file.nonce,
            content_type: file.type || 'application/octet-stream',
            wrapped_keys: sealed.wrapped_keys,
        });
        form.append(seal);
        form.dataset.sealed = '1';
        form.requestSubmit();
    }

    document.addEventListener('DOMContentLoaded', () => {
        const account = accountData();
        if (account) {
            getDeviceKey(account.fingerprints)
                .then((existing) => {
                    if (existing) {
                        return openSealedContent(document);
                    }
                    return ensureDeviceKey(account).then(() => {
                        location.reload();
                    });
                })
                .catch(() => {});
        }
        document.body.addEventListener('htmx:afterSwap', (event) => {
            openSealedContent(event.target).catch(() => {});
        });
        document.addEventListener('submit', (event) => {
            const form = event.target;
            if (!form.matches || !form.matches('[data-seal-prescription]')) {
                return;
            }
            if (form.dataset.sealed === '1' || form.querySelector('[name=remove]')) {
                return;
            }
            event.preventDefault();
            sealPrescriptionForm(form).catch(() => {});
        });
        document.body.addEventListener('htmx:confirm', (event) => {
            const form = event.detail.elt;
            if (!form.matches || !form.matches('[data-chat-form]')) {
                return;
            }
            const field = form.querySelector('textarea');
            if (!field || field.dataset.sealed === '1') {
                return;
            }
            event.preventDefault();
            sealChatForm(form)
                .then(() => event.detail.issueRequest(true))
                .catch(() => {});
        });
    });

    window.E2EE = Object.freeze({
        keys: Object.freeze({
            generateDeviceKeyPair,
            exportPublicKey,
            importPublicKey,
            fingerprintPublicKey,
            createDeviceKey,
            getDeviceKey,
            ensureDeviceKey,
        }),
        messages: Object.freeze({
            decodeBase64,
            generateDataKey,
            encryptBytes,
            decryptBytes,
            wrapDataKey,
            unwrapDataKey,
            encryptShared,
            encryptEnvelope,
            encryptMessage,
            decryptEnvelope,
            encryptAttachment,
            decryptAttachment,
        }),
    });
})();
