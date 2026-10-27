(() => {
    'use strict';

    const draftDatabase = 'magistral-order-draft';
    const prescriptionExtensions = ['pdf', 'jpg', 'jpeg', 'png'];
    const prescriptionMaxBytes = 10 * 1024 * 1024;

    function openStore(mode) {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(draftDatabase, 1);
            request.onupgradeneeded = () => {
                request.result.createObjectStore('draft');
            };
            request.onerror = () => reject(request.error);
            request.onsuccess = () => {
                resolve(
                    request.result.transaction('draft', mode).objectStore('draft'),
                );
            };
        });
    }

    function requestResult(request) {
        return new Promise((resolve, reject) => {
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    async function readDraft() {
        const store = await openStore('readonly');
        return requestResult(store.get('current'));
    }

    async function saveDraft(draft) {
        const store = await openStore('readwrite');
        await requestResult(store.put(draft, 'current'));
    }

    async function clearDraft() {
        const store = await openStore('readwrite');
        await requestResult(store.delete('current'));
    }

    function field(form, name) {
        return form.querySelector(`[name="${name}"]`);
    }

    function envelope(part, wrappedKeys) {
        return JSON.stringify({
            ciphertext: part.ciphertext,
            nonce: part.nonce,
            wrapped_keys: wrappedKeys,
        });
    }

    async function publicKeys(prepared) {
        const keys = prepared.public_keys.map((key) => key.public_key);
        const accountNode = document.getElementById('e2ee-account');
        if (!accountNode) {
            return keys;
        }
        const deviceKey = await window.E2EE.keys.ensureDeviceKey(
            JSON.parse(accountNode.textContent),
        );
        if (!keys.includes(deviceKey.publicKey)) {
            keys.push(deviceKey.publicKey);
        }
        return keys;
    }

    async function storeOrderForm(form) {
        const fileInput = field(form, 'prescription_file');
        const file = fileInput.files[0];
        if (file) {
            const extension = file.name.split('.').pop().toLowerCase();
            const invalid = !prescriptionExtensions.includes(extension)
                || file.size > prescriptionMaxBytes;
            if (invalid) {
                fileInput.setCustomValidity(
                    'La receta tiene que ser un PDF, JPG o PNG de hasta 10 MB.',
                );
                fileInput.reportValidity();
                return;
            }
            fileInput.setCustomValidity('');
        }
        const previous = await readDraft();
        const cleared = field(form, 'clear_prescription').value === '1';
        let storedFile = null;
        if (file) {
            storedFile = {
                name: file.name,
                type: file.type,
                bytes: await file.arrayBuffer(),
            };
        } else if (!cleared && previous && previous.file) {
            storedFile = previous.file;
        }
        await saveDraft({
            formula: field(form, 'formula').value,
            presentation: field(form, 'presentation').value,
            note: field(form, 'note').value,
            file: storedFile,
        });
        if (storedFile) {
            field(form, 'has_prescription').value = '1';
        }
        for (const name of ['formula', 'presentation', 'note', 'prescription_file']) {
            field(form, name).disabled = true;
        }
        form.dataset.stored = '1';
        form.submit();
    }

    async function confirmOrder(form) {
        const draft = await readDraft();
        const summary = document.querySelector('[data-order-draft-summary]');
        if (!draft || !draft.formula || !draft.presentation) {
            if (summary) {
                summary.textContent = 'Volvé a cargar la preparación antes de enviarla.';
            }
            return;
        }
        const prepare = await fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
            headers: {
                'X-Order-Prepare': '1',
                'X-CSRFToken': field(form, 'csrfmiddlewaretoken').value,
            },
        });
        const contentType = prepare.headers.get('content-type') || '';
        if (!prepare.ok || !contentType.includes('application/json')) {
            if (summary) {
                summary.textContent = 'No pudimos preparar la solicitud.';
            }
            return;
        }
        const prepared = await prepare.json();
        const parts = {
            formula: draft.formula,
            presentation: draft.presentation,
        };
        if (draft.note) {
            parts.note = draft.note;
        }
        if (draft.file) {
            parts.filename = draft.file.name;
            parts.file = draft.file.bytes;
        }
        const sealed = await window.E2EE.messages.encryptShared(
            parts,
            await publicKeys(prepared),
        );
        const body = new FormData();
        body.set('csrfmiddlewaretoken', field(form, 'csrfmiddlewaretoken').value);
        body.set('formula', envelope(sealed.encrypted.formula, sealed.wrapped_keys));
        body.set(
            'presentation',
            envelope(sealed.encrypted.presentation, sealed.wrapped_keys),
        );
        body.set(
            'note',
            draft.note ? envelope(sealed.encrypted.note, sealed.wrapped_keys) : '',
        );
        if (draft.file) {
            const bytes = window.E2EE.messages.decodeBase64(
                sealed.encrypted.file.ciphertext,
            );
            body.set('prescription_file', new File([bytes], 'prescription.bin'));
            body.set('prescription_seal', JSON.stringify({
                encrypted_filename: sealed.encrypted.filename.ciphertext,
                filename_nonce: sealed.encrypted.filename.nonce,
                nonce: sealed.encrypted.file.nonce,
                content_type: draft.file.type || 'application/octet-stream',
                wrapped_keys: sealed.wrapped_keys,
            }));
        }
        const saved = await fetch(prepared.seal_url, {
            method: 'POST',
            body,
            headers: {
                'X-CSRFToken': field(form, 'csrfmiddlewaretoken').value,
            },
        });
        if (!saved.ok) {
            if (summary) {
                summary.textContent = 'No pudimos cifrar la solicitud.';
            }
            return;
        }
        const result = await saved.json();
        await clearDraft();
        window.location.assign(result.next_url);
    }

    document.addEventListener('DOMContentLoaded', () => {
        const orderForm = document.querySelector('[data-order-form]');
        if (orderForm) {
            if (orderForm.hasAttribute('data-restore-draft')) {
                readDraft().then((draft) => {
                    if (!draft) {
                        return;
                    }
                    field(orderForm, 'formula').value = draft.formula || '';
                    field(orderForm, 'presentation').value = draft.presentation || '';
                    field(orderForm, 'note').value = draft.note || '';
                    const picker = orderForm.querySelector('[x-data]');
                    if (draft.file && picker && window.Alpine) {
                        window.Alpine.$data(picker).savedName = draft.file.name;
                    }
                }).catch(() => {});
            }
            orderForm.addEventListener('submit', (event) => {
                if (orderForm.dataset.stored === '1') {
                    return;
                }
                if (!orderForm.reportValidity()) {
                    return;
                }
                event.preventDefault();
                storeOrderForm(orderForm).catch(() => {});
            });
        }

        const confirmForm = document.querySelector('[data-order-confirm]');
        if (confirmForm) {
            readDraft().then((draft) => {
                const summary = document.querySelector('[data-order-draft-summary]');
                if (!summary || !draft) {
                    return;
                }
                const file = draft.file ? ' · receta adjunta' : '';
                summary.textContent = `${draft.formula} · ${draft.presentation}${file}`;
            }).catch(() => {});
            confirmForm.addEventListener('submit', (event) => {
                if (!confirmForm.querySelector('[name="pharmacy"]:checked')) {
                    return;
                }
                event.preventDefault();
                confirmOrder(confirmForm).catch(() => {});
            });
        }

        const discard = document.querySelector('[data-order-discard]');
        if (discard) {
            discard.addEventListener('submit', () => {
                clearDraft().catch(() => {});
            });
        }
    });
})();
