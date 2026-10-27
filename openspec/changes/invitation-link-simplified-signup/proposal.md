# Proposal

## Why

El flujo actual de registro por link de invitación pide demasiados datos (nombre, apellido, contraseña) y muestra opciones irrelevantes como "Registrarse con Google". El objetivo es hacer el ingreso lo más directo posible: un click para entrar la primera vez, y un flujo claro para recuperar el acceso si se pierde la sesión.

## What Changes

- El formulario de registro por invitación se reemplaza por una pantalla mínima: solo el email (readonly, pre-completado) y un botón "Continuar".
- Al confirmar, se crea la cuenta automáticamente con contraseña no usable (`set_unusable_password`) y campos de nombre/apellido vacíos.
- Mientras la sesión esté activa, reusar el link redirige directamente al destino sin mostrar ningún formulario.
- Si el usuario pierde la sesión y vuelve a usar el link, se detecta que la cuenta existe pero no tiene credenciales de login. Se muestra una pantalla para establecer contraseña **o** vincular su cuenta de Google.
- Una vez que la cuenta tiene contraseña usable o cuenta Google vinculada, el link de invitación ya no ofrece registro: redirige directamente al login estándar (con `next` hacia el destino).

## Capabilities

### New Capabilities

- `invitation/simplified-signup`: Flujo de registro simplificado por link de invitación con cuatro estados: autenticado → directo, sin cuenta → alta automática, cuenta sin credenciales → completar cuenta, cuenta completa → login estándar.

### Modified Capabilities

_(ninguna — el flujo de invitación no tenía spec previa)_

## Impact

- `src/accounts/views.py`: `InvitationSignupView` reemplaza su lógica actual (hereda de `SignupView` de allauth) por lógica propia con los cuatro estados.
- `src/accounts/forms/signup.py`: `SignupForm` deja de usarse en el flujo de invitación (puede simplificarse o eliminarse en el futuro si no se usa en otro lugar).
- `src/accounts/commands/signup.py`: nuevo command `create_account_from_invitation` para alta rápida sin contraseña.
- Nuevos templates: `accounts/invitation_confirm.html` (Estado 1: email + Continuar) y `accounts/invitation_complete_account.html` (Estado 3: establecer contraseña o Google).
- `src/accounts/tests/test_invitation.py`: actualización de tests existentes y nuevos escenarios.
- No hay cambios de modelo ni de migraciones.
