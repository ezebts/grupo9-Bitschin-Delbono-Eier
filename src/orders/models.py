from django.db import models


class PreparationType(models.TextChoices):
    SOLUTION = 'solution', 'Solución / loción'
    CAPSULES = 'capsules', 'Cápsulas'
    CREAM = 'cream', 'Crema / pomada / gel'
    SYRUP = 'syrup', 'Jarabe / suspensión'
    OVULES = 'ovules', 'Óvulos / supositorios'
    OTHER = 'other', 'Otra'


class Urgency(models.TextChoices):
    AS_SOON_AS_POSSIBLE = 'as_soon_as_possible', 'Lo antes posible'
    THIS_WEEK = 'this_week', 'Esta semana'
    NO_RUSH = 'no_rush', 'Sin apuro'


class DeliveryPreference(models.TextChoices):
    PICKUP = 'pickup', 'Retiro en farmacia'
    HOME_DELIVERY = 'home_delivery', 'Envío a domicilio'
