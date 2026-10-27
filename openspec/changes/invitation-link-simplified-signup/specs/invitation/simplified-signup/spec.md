# Spec Delta

## Purpose

Define el comportamiento del flujo de registro e ingreso a través de links de invitación, desde el alta automática en el primer uso hasta el login estándar cuando la cuenta ya está completamente configurada.

## ADDED Requirements

### Requirement: Usuario autenticado es redirigido directamente
Si el usuario que accede al link de invitación ya tiene una sesión activa, el sistema SHALL redirigirlo al `next_url` del link (o al home si no hay `next_url`) sin mostrar ningún formulario.

#### Scenario: Usuario logueado reutiliza el link
- **WHEN** un usuario con sesión activa accede a un link de invitación válido
- **THEN** el sistema lo redirige al destino configurado en el link sin mostrar formulario alguno

### Requirement: Primera vez — alta automática por confirmación de email
Cuando el email del link de invitación no corresponde a ninguna cuenta existente, el sistema SHALL mostrar un formulario mínimo con el email pre-completado (solo lectura) y un botón "Continuar". Al confirmar, el sistema crea la cuenta con contraseña no usable, first_name y last_name vacíos, loguea al usuario automáticamente y redirige al destino del link.

#### Scenario: Pantalla de confirmación simplificada
- **WHEN** se accede al link y no existe cuenta con ese email
- **THEN** se muestra el email readonly y el botón "Continuar" (sin campos de nombre, apellido ni contraseña)

#### Scenario: Alta y login automático al confirmar
- **WHEN** el usuario presiona "Continuar" en el formulario de confirmación
- **THEN** se crea la cuenta (sin contraseña usable, role y cuentas asociadas según el link), el usuario queda logueado y es redirigido al destino del link

### Requirement: Cuenta sin credenciales — pantalla para completar cuenta
Cuando el email del link corresponde a una cuenta existente que no tiene contraseña usable ni cuenta Google vinculada, el sistema SHALL mostrar una pantalla que permita al usuario establecer una contraseña o vincular su cuenta de Google. Al completar cualquiera de las dos opciones, el usuario queda logueado y es redirigido al destino del link.

#### Scenario: Detección de cuenta sin credenciales de login
- **WHEN** se accede al link y existe una cuenta con ese email sin contraseña usable y sin Google vinculado
- **THEN** se muestra la pantalla para completar la cuenta (establecer contraseña o vincular Google)

#### Scenario: Establecer contraseña completa el acceso
- **WHEN** el usuario ingresa y confirma una contraseña válida en la pantalla de completar cuenta
- **THEN** la contraseña queda guardada, el usuario queda logueado y es redirigido al destino del link

#### Scenario: Vincular Google completa el acceso
- **WHEN** el usuario elige vincular su cuenta de Google en la pantalla de completar cuenta
- **THEN** al finalizar el flujo OAuth, la cuenta queda vinculada, el usuario queda logueado y es redirigido al destino del link

### Requirement: Cuenta completa — redirección al login estándar
Cuando el email del link corresponde a una cuenta existente que ya tiene contraseña usable o cuenta Google vinculada, el sistema SHALL redirigir al usuario a la pantalla de login estándar con el destino del link como `next`.

#### Scenario: Redirección a login cuando la cuenta ya está configurada
- **WHEN** se accede al link y la cuenta tiene contraseña usable o Google vinculado
- **THEN** el sistema redirige a la pantalla de login con `next` apuntando al destino del link

### Requirement: Link inválido muestra error y redirige al signup estándar
Si el link de invitación no puede ser verificado (firma inválida, expirado, malformado), el sistema SHALL mostrar un mensaje de error y redirigir a la pantalla de signup estándar.

#### Scenario: Link con firma inválida
- **WHEN** se accede al endpoint de invitación con un token malformado o expirado
- **THEN** se muestra un mensaje de error y se redirige al signup estándar
