from app.moderacion import Filtro

FILTRO = Filtro(["desnud*", "nude", "porn*", "sexo", "gore", "sangre a chorros"])


def test_bloquea_palabras_y_prefijos_sin_importar_tildes_ni_mayusculas():
    assert FILTRO.bloqueada("Una persona DESNUDA en la playa") == "desnuda"
    assert FILTRO.bloqueada("PORNOGRAFÍA") == "pornografia"
    assert FILTRO.bloqueada("un nude") == "nude"
    assert FILTRO.bloqueada("con sangre a chorros") == "sangre a chorros"


def test_no_bloquea_palabras_parecidas():
    assert FILTRO.bloqueada("Un nudo marinero") is None
    assert FILTRO.bloqueada("El sexto carnaval") is None
    assert FILTRO.bloqueada("Una gorra de colores") is None
