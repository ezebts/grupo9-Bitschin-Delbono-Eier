# Tasks

## 1. Command de alta rápida

- [x] 1.1 Crear `src/accounts/commands/create_account_from_invitation.py` con la función `create_account_from_invitation(invitation)` que crea el `User` con `set_unusable_password()`, `first_name=''`, `last_name=''`, aplica el rol y crea el `ClientAccount` o `PharmacyAccount` según el link (reutilizando la lógica de `signup_with_invitation`). Verificar con un test unitario que el user creado tiene `has_usable_password() == False` y el account correspondiente.

## 2. Vista `InvitationSignupView` con los cuatro estados

- [x] 2.1 Reescribir `InvitationSignupView` en `src/accounts/views.py` para que ya no herede de `SignupView` de allauth sino de `View`. El método `dispatch` implementa la máquina de estados:
  - Estado 0 (link inválido): error + redirect a `account_signup` (comportamiento actual, sin cambios).
  - Estado autenticado: redirect a `next_url` o home.
  - Estado "primera vez": GET muestra template de confirmación; POST llama a `create_account_from_invitation`, loguea y redirige.
  - Estado "cuenta sin credenciales": GET muestra template de completar cuenta; POST valida contraseña, la setea, loguea y redirige.
  - Estado "cuenta completa": redirect a login con `next=next_url`.
  Verificar que los tests existentes en `test_invitation.py` siguen pasando (adaptarlos donde sea necesario).

- [x] 2.2 Agregar helper privado `_account_is_complete(user)` que devuelve `True` si `user.has_usable_password()` o `user.socialaccount_set.filter(provider='google').exists()`. Verificar con test unitario los tres casos (sin contraseña sin google → False, con contraseña → True, con google → True).

## 3. Templates

- [x] 3.1 Crear `src/accounts/templates/accounts/invitation_confirm.html`: extiende `allauth/layouts/base.html`, muestra el email como texto (no input), botón "Continuar" que hace POST al mismo endpoint. Verificar que al hacer GET con un email que no existe, la respuesta contiene el email y no contiene `name="password1"`.

- [x] 3.2 Crear `src/accounts/templates/accounts/invitation_complete_account.html`: extiende `allauth/layouts/base.html`, muestra email como texto (no input), campo `password1` y `password2`, botón "Continuar", y botón de Google (reusar `accounts/_google_button.html`) con el `next_url` del link como `next`. Verificar que al hacer GET con una cuenta sin credenciales, la respuesta contiene los campos de contraseña y el botón de Google.

## 4. Tests de los nuevos escenarios

- [x] 4.1 Agregar test `test_invitation_autenticado_redirige_directo`: usuario logueado accede al link → respuesta es redirect 302 al `next_url`. Verificar que no se muestra ningún formulario.

- [x] 4.2 Agregar test `test_invitation_primera_vez_post_crea_cuenta_y_loguea`: POST al endpoint de confirmación → se crea el user con `has_usable_password() == False`, la sesión queda autenticada y la respuesta redirige al `next_url`.

- [x] 4.3 Agregar test `test_invitation_cuenta_sin_credenciales_establece_password`: existe user sin contraseña usable ni Google; POST con password válida → `user.has_usable_password() == True`, sesión autenticada, redirect a `next_url`.

- [x] 4.4 Agregar test `test_invitation_cuenta_completa_redirige_a_login`: existe user con contraseña usable → GET redirige a login con `next` correcto. Repetir para user con Google vinculado.

## Workflow follow-up

- Revisar manualmente el flujo completo en el ambiente local con un link de invitación de farmacia y de cliente.
- Archivar el change una vez aprobado en review.
