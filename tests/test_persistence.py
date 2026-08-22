"""Tests de la capa de persistencia y trazabilidad (SDD sección 15)."""

from grain_quality.calculator import calculate_ctg
from grain_quality.models import MeasurementInput
from grain_quality.persistence import Repository


def test_guardado_y_trazabilidad(tmp_path):
    repo = Repository(tmp_path / "test.db")
    result = calculate_ctg(
        "SOJA",
        [MeasurementInput("humedad", plant_value=14.2, chamber_value=13.8),
         MeasurementInput("materias_extranas", plant_value=1.5)],
        contract="10001", ctg="CTG01", weight_tn=30,
    )
    calc_id = repo.save_calculation(result)

    stored = repo.get_calculation(calc_id)
    assert stored["contract"] == "10001"
    assert stored["ctg"] == "CTG01"
    assert stored["norm_version"]
    assert stored["calculated_at"]

    details = repo.get_details(calc_id)
    humedad = next(d for d in details if d["rubro_code"] == "humedad")
    assert humedad["plant_value"] == 14.2
    assert humedad["chamber_value"] == 13.8
    assert humedad["selected_value"] == 13.8
    assert humedad["selected_source"] == "CAMARA"
    assert humedad["rule"]

    assert repo.list_calculations()[0]["calculation_id"] == calc_id
    repo.close()
