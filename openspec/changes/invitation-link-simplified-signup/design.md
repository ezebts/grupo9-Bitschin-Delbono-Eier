# Design

## Context

Ver `proposal.md – Why` para la motivación.

`InvitationSignupView` extiende actualmente `SignupView` de allauth y delega en `SignupForm` (con campos nombre, apellido, contraseña) para crear la cuenta. El link de invitación porta rol, email, `next_url` y `details` (e.g., `pharmacy_id`) firmados con `django.core.signing`. El estado de "tiene contraseña" se puede leer con `user.has_usable_password()` (API de Django). El estado de "tiene Google vinculado" se puede leer con `user.socialaccount_set.filter(provider='google').exists()`.

## Goals / Non-Goals

**Goals:**
- Reemplazar la lógica de `InvitationSignupView` por una máquina de cuatro estados sin tocar `SignupView` ni el flow de signup estándar.
- Crear la cuenta en el backend sin pasar por el form de allauth (contraseña temporal = `set_unusable_password()`).
- Loguear al usuario automáticamente después del alta o del setup de contraseña.

**Non-Goals:**
- No cambiar `SignupView` ni el signup estándar (sin invitación).
- No agregar campos de nombre/apellido en ninguno de los nuevos formularios.
- No cambiar la estructura del `InvitationLink` ni sus firmas.

## Decisions

### D1 — `InvitationSignupView` deja de heredar de `SignupView`

**Decisión**: Reemplazar la herencia con una `View` (o `FormView`) propia.  
**Rationale**: `SignupView` de allauth asume que el usuario no está autenticado y que hay un formulario completo. Los cuatro estados requieren lógica de dispatch que va en contra de esas asunciones. Heredar e intentar sobreescribir varios métodos sería más frágil que tener una vista propia y simple.  
**Alternativa descartada**: Mantener la herencia y sobreescribir `dispatch` + `get`/`post`. Descartada porque cada estado tiene un form diferente (o ninguno), lo que obliga a anular demasiados métodos de allauth.

### D2 — Cuenta sin contraseña usable con `set_unusable_password()`

**Decisión**: Al crear la cuenta en el primer uso del link, llamar `user.set_unusable_password()` en lugar de generar una contraseña aleatoria.  
**Rationale**: Es la API idiomática de Django para cuentas que aún no tienen contraseña. `user.has_usable_password()` devuelve `False`, lo que actúa como señal confiable para el Estado 3. Allauth ya soporta este estado (lo usa para usuarios de social login).  
**Alternativa descartada**: Contraseña aleatoria + campo booleano en `User`. Requeriría migración y es información redundante con lo que `has_usable_password()` ya provee.

### D3 — Login automático con `login()` de Django tras el alta

**Decisión**: Tras crear la cuenta (Estado 1) o tras establecer la contraseña (Estado 3 vía form), llamar `django.contrib.auth.login(request, user, backend=...)` directamente.  
**Rationale**: Es la forma estándar del proyecto (lo usa allauth internamente). Evita redirigir al login y volver.  
**Backend**: `'allauth.account.auth_backends.AuthenticationBackend'` (ya configurado en `AUTHENTICATION_BACKENDS`).

### D4 — Estado 3 con Google: delegar en el flujo OAuth existente de allauth

**Decisión**: El botón de Google en la pantalla de "completar cuenta" apunta al mismo flujo de login social de allauth. La configuración `SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True` se encarga de vincular la cuenta existente cuando el email coincide.  
**Rationale**: No requiere código adicional del lado del servidor. El redirect `next` lleva al usuario al destino del link después del flujo OAuth.  
**Consideración**: El link de invitación completo (con `next_url`) se pasa como parámetro `next` al iniciar el OAuth, no la URL de invitación (para no re-procesar el link después del OAuth).

### D5 — Command `create_account_from_invitation` en `accounts/commands/`

**Decisión**: Extraer la lógica de alta a un command nuevo en lugar de hacerlo inline en la vista.  
**Rationale**: Consistencia con el patrón del proyecto (`signup_with_invitation` ya existe como command). Facilita testeo unitario.

### D6 — Formulario de establecer contraseña: form Django propio (sin allauth `PasswordSetView`)

**Decisión**: Form Django simple con `password1` y `password2`, procesado en una acción POST de `InvitationSignupView`.  
**Rationale**: `PasswordSetView` de allauth requiere usuario autenticado (`LoginRequiredMixin`). En el Estado 3 el usuario no está logueado; necesitamos autenticarlo nosotros mismos tras el set de contraseña. Un form propio es más directo.  
**Alternativa descartada**: Autenticar al usuario temporalmente en sesión antes de redirigir a `PasswordSetView`. Añade un paso innecesario y complejidad de sesión.

## Risks / Trade-offs

- **Login automático sin verificación de email** → El proyecto ya no requiere verificación de email (allauth `EMAIL_VERIFICATION = 'none'` o similar). Asumir que el email del link es confiable dado que está firmado digitalmente.
- **Estado 3 con Google: el `next` llega al destino pero el link no se re-procesa** → Después del OAuth, allauth redirige al `next` directamente. El usuario llega logueado al destino. Si por alguna razón el link expira entre el Estado 1 y el Estado 3, el flujo de Google no re-valida el link — pero eso está bien, porque la cuenta ya existe.
- **`first_name` / `last_name` vacíos** → Las vistas que muestran el nombre del usuario deben tolerar nombres vacíos (ya lo hacen: `get_initials()` lo maneja).
