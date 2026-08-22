"""Smoke tests de la interfaz web (carga manual e importación)."""

import io

import pytest
from openpyxl import Workbook


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from grain_quality import webapp
    from grain_quality.persistence import Repository

    monkeypatch.setattr(webapp, "repository", Repository(tmp_path / "web.db"))
    monkeypatch.setattr(webapp, "EXPORTS_DIR", tmp_path)
    webapp.app.config["TESTING"] = True
    with webapp.app.test_client() as test_client:
        yield test_client


def test_pantalla_carga_manual(client):
    response = client.get("/?producto=SOJA")
    assert response.status_code == 200
    assert "Humedad" in response.get_data(as_text=True)


def test_calculo_manual(client):
    response = client.post("/calcular", data={
        "producto": "SOJA",
        "contrato": "10001",
        "ctg": "CTG01",
        "toneladas": "30",
        "humedad__planta": "14,2",
        "humedad__camara": "13,8",
        "materias_extranas__planta": "2,5",
    })
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "13.8" in html            # valor válido = Cámara
    assert "CAMARA" in html
    assert "PLANTA" in html          # materias extrañas usó Planta
    assert "-1.50 %" in html         # rebaja ME: (2.5 - 1.0) * 1


def test_importacion_web(client):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Contrato", "CTG", "Producto", "Toneladas",
                  "Humedad Planta", "Humedad Camara"])
    sheet.append(["10001", "CTG01", "SOJA", 30, 14.2, 13.8])
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)

    response = client.post(
        "/importar",
        data={"archivo": (buffer, "datos.xlsx")},
        content_type="multipart/form-data",
    )
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Contrato 10001" in html
    assert "Descargar resultados" in html


def test_historial(client):
    client.post("/calcular", data={"producto": "SOJA", "humedad__planta": "14"})
    response = client.get("/historial")
    assert response.status_code == 200
    assert "Soja" in response.get_data(as_text=True)


def test_normas(client):
    response = client.get("/normas")
    assert response.status_code == 200
    assert "Girasol" in response.get_data(as_text=True)
