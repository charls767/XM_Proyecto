"""Proceso semanal: explicación exacta, monitoreo y registro inmutable."""

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import config  # noqa: E402
import feature_engineering as fe  # noqa: E402
import models  # noqa: E402
import monitoreo  # noqa: E402
import semanal  # noqa: E402

SEMANAL = RAIZ / "data" / "processed" / "semanal_corregida.parquet"
pytestmark = pytest.mark.skipif(not SEMANAL.exists(), reason="falta la tabla semanal corregida")


@pytest.fixture(scope="module")
def d():
    return fe.preparar(pd.read_parquet(SEMANAL))


def test_explicacion_suma_el_pronostico(d):
    ent = d.dropna(subset=config.VARIABLES + ["y"])
    ent = ent[ent.index < "2022-01-01"]
    m = models.ridge().fit(ent[config.VARIABLES], ent.y)
    fila = d.loc["2023-06-05"]
    intercepto, aportes = semanal.contribuciones(m, fila)
    pred = m.predict(d.loc[["2023-06-05"], config.VARIABLES])[0]
    assert intercepto + aportes.sum() == pytest.approx(pred, abs=1e-10)


def test_dato_faltante_pasa_a_respaldo(d):
    semana = d.index[-2]
    roto = d.copy()
    roto.loc[semana, "embalse_cambio"] = np.nan
    controles = monitoreo.calidad(roto, semana, semana + pd.Timedelta(days=8))
    estado, motivos = monitoreo.estado(controles, monitoreo.fuera_de_rango(roto, semana), {"semanas": 0})
    assert estado == "respaldo"
    assert any("embalse_cambio" in m for m in motivos)


def test_detecta_extrapolacion(d):
    semana = d.index[-2]
    raro = d.copy()
    raro.loc[semana, "aportes_pct_media_4s"] = d.aportes_pct_media_4s.max() + 1
    rango = monitoreo.fuera_de_rango(raro, semana)
    assert "aportes_pct_media_4s" in set(rango.loc[rango.nivel == "extrapolacion", "variable"])
    estado, _ = monitoreo.estado(monitoreo.calidad(raro, semana, semana + pd.Timedelta(days=8)), rango, {"semanas": 0})
    assert estado == "vigilancia"


def test_desempeno_bajo_pide_vigilancia():
    idx = pd.date_range("2025-01-06", periods=30, freq="W-MON")
    h = pd.DataFrame({"real": 100.0, "ingenuo": 101.0, "prediccion": 120.0, "cota": 90.0}, index=idx)
    des = monitoreo.desempeno_reciente(h)
    assert des["razon_mae"] > 1 and des["cobertura"] == 0
    estado, motivos = monitoreo.estado(pd.DataFrame(columns=["control", "estado", "detalle"]), pd.DataFrame(columns=["nivel"]), des)
    assert estado == "vigilancia" and len(motivos) == 3  # MAE, cobertura y sesgo (+20 %)
    assert any("se pasó" in m for m in motivos)


def _historial(errores, real=500.0):
    idx = pd.date_range("2025-01-06", periods=len(errores), freq="W-MON")
    e = np.asarray(errores, dtype=float)
    return pd.DataFrame({"real": real, "ingenuo": real + 80 * np.sign(np.sin(np.arange(len(e)) + 0.5)),
                         "prediccion": real + e, "cota": real + 200}, index=idx)


def test_sesgo_significativo_pide_vigilancia():
    rng = np.random.default_rng(0)
    des = monitoreo.desempeno_reciente(_historial(-55 + rng.normal(0, 40, 26)))  # ≈ −11 % del precio
    assert des["p_sesgo"] < 0.05 and monitoreo.sesgo_significativo(des)
    estado, motivos = monitoreo.estado(pd.DataFrame(columns=["control", "estado", "detalle"]),
                                       pd.DataFrame(columns=["nivel"]), des)
    assert estado == "vigilancia" and any("se quedó corto" in m for m in motivos)


def test_sesgo_pequeno_o_ruidoso_no_alarma():
    rng = np.random.default_rng(1)
    pequeno = monitoreo.desempeno_reciente(_historial(-10 + rng.normal(0, 5, 26)))  # 2 %, significativo
    ruidoso = monitoreo.desempeno_reciente(_historial(-30 + rng.normal(0, 200, 26)))  # 6 %, no significativo
    assert pequeno["p_sesgo"] < 0.05 and not monitoreo.sesgo_significativo(pequeno)
    assert ruidoso["p_sesgo"] > 0.05 and not monitoreo.sesgo_significativo(ruidoso)


@pytest.mark.parametrize("dias_oferta, esperado", [(0, "ok"), (1, "nota"), (2, "aviso")])
def test_series_deben_cubrir_la_semana_base(d, dias_oferta, esperado):
    semana = d.index[-2]
    domingo = semana + pd.Timedelta(days=6)
    fechas = {s: domingo + pd.Timedelta(days=2) for s in config.SERIES_SEMANA_BASE}
    fechas["oferta"] = domingo - pd.Timedelta(days=dias_oferta)
    controles = monitoreo.calidad(d, semana, semana + pd.Timedelta(days=9), datos_hasta=fechas)
    fila = controles.set_index("control").loc["Series al día"]
    assert fila.estado == esperado
    if dias_oferta:
        assert "oferta" in fila.detalle
    estado, motivos = monitoreo.estado(controles, pd.DataFrame(columns=["nivel"]), {"semanas": 0})
    assert any("Series al día" in m for m in motivos) == (esperado == "aviso")


def test_emision_se_reconstruye_desde_el_snapshot():
    """Prueba de humo de punta a punta (sin API ni registro) y reproducción sin datos."""
    import json

    r = semanal.emitir(actualizar=False, guardar=False)
    assert r["estado"] in ("normal", "vigilancia", "respaldo")
    assert "Series al día" in set(r["controles"].control)
    if r["estado"] == "respaldo":
        pytest.skip("en respaldo no hay modelo que reconstruir")
    snap = json.loads(json.dumps({"variables": r["variables"], "reproduccion": r["reproduccion"]}, default=semanal._json))
    pron, cota, cota_vol = semanal.reproducir(snap, r["precio_base"])
    assert pron == pytest.approx(r["pronostico"], rel=1e-10)
    assert cota == pytest.approx(r["cota90"], rel=1e-10) and cota_vol == pytest.approx(r["cota90_vol"], rel=1e-10)
    assert len(r["reproduccion"]["huella_entrenamiento"]) == 64


def _emision(semana, pronostico):
    return {"fecha_emision": semana + pd.Timedelta(days=8), "semana_base": semana,
            "semana_objetivo": semana + pd.Timedelta(weeks=1), "version_modelo": "prueba", "estado": "normal",
            "motivos": [], "datos_hasta": {"precio": semana + pd.Timedelta(days=6)}, "precio_base": 100.0,
            "pronostico": pronostico, "cambio_pct": pronostico - 100, "cota90": 150.0, "cota90_vol": 160.0,
            "ingenuo": 100.0, "alertas": {"salto": {"puntaje": 0.1}}, "variables": {},
            "controles": pd.DataFrame(columns=["control", "estado", "detalle"])}


def test_registro_no_sobrescribe_y_califica(tmp_path, monkeypatch, d):
    monkeypatch.setattr(semanal, "REGISTRO", tmp_path)
    monkeypatch.setattr(semanal, "ARCHIVO", tmp_path / "pronosticos.csv")
    semana = d.index[-3]
    assert semanal.registrar(_emision(semana, 90.0)) is True
    assert semanal.registrar(_emision(semana, 999.0)) is False
    reg = semanal._leer_registro()
    assert len(reg) == 1 and reg.pronostico.iloc[0] == 90.0
    reg = semanal.calificar(d)
    real = d.precio[semana + pd.Timedelta(weeks=1)]
    assert reg.real.iloc[0] == pytest.approx(real, abs=0.01)
    assert bool(reg.cubierto.iloc[0]) == (real <= 150.0)


def test_candidato_se_registra_y_califica_aparte(tmp_path, monkeypatch, d):
    monkeypatch.setattr(semanal, "REGISTRO", tmp_path)
    monkeypatch.setattr(semanal, "ARCHIVO", tmp_path / "pronosticos.csv")
    semana = d.index[-3]
    previa = d.index[-4]
    # Fila anterior sin candidato, como la primera emisión real.
    semanal.registrar(_emision(previa, 90.0))
    conc = _emision(semana, 95.0)
    conc["candidato"] = {"version": "prueba", "pronostico": 80.0, "cota90": 1.0}
    semanal.registrar(conc)
    reg = semanal.calificar(d)
    assert reg.pronostico.tolist() == [90.0, 95.0]
    assert pd.isna(reg.candidato_error.iloc[0]) and pd.isna(reg.candidato_cubierto.iloc[0])
    real = d.precio[semana + pd.Timedelta(weeks=1)]
    assert reg.candidato_error.iloc[1] == pytest.approx(80.0 - real, abs=0.01)
    assert bool(reg.candidato_cubierto.iloc[1]) is False


def test_candidato_cmg_se_registra_sella_y_califica(tmp_path, monkeypatch, d):
    monkeypatch.setattr(semanal, "REGISTRO", tmp_path)
    monkeypatch.setattr(semanal, "ARCHIVO", tmp_path / "pronosticos.csv")
    semana = d.index[-3]
    semanal.registrar(_emision(d.index[-4], 90.0))  # fila anterior sin el candidato nuevo
    conc = _emision(semana, 95.0)
    conc["candidato_cmg"] = {"version": "cmg-prueba", "pronostico": 85.0, "cota90": 1e6}
    semanal.registrar(conc)
    reg = semanal.calificar(d)
    real = d.precio[semana + pd.Timedelta(weeks=1)]
    assert pd.isna(reg.candidato_cmg_error.iloc[0])
    assert reg.candidato_cmg_error.iloc[1] == pytest.approx(85.0 - real, abs=0.01)
    assert bool(reg.candidato_cmg_cubierto.iloc[1]) is True
    assert semanal.verificar_registro() == []
    reg.loc[1, "candidato_cmg_pronostico"] = 86.0  # lo emitido por el candidato también está sellado
    semanal._escribir(reg)
    assert semanal.verificar_registro() == [f"{semana:%Y-%m-%d}"]


def test_columnas_nuevas_no_cambian_las_huellas_del_registro_real():
    """Las filas emitidas antes del candidato con costo marginal deben seguir verificando."""
    if not semanal.ARCHIVO.exists():
        pytest.skip("sin registro")
    assert semanal.verificar_registro() == []


def test_candidato_cmg_solo_usa_dias_publicados(d):
    import xm_client as xm

    cmg = xm.leer_cache("costo_marginal")
    if cmg.empty:
        pytest.skip("sin caché de costo marginal")
    semana = d.index[-3]
    lunes = semana + pd.Timedelta(weeks=1)
    con = semanal.candidato_cmg(d, semana, float(d.precio[semana]), actualizar=False)
    assert sorted(con["cmg_publicado"]) == [f"{lunes:%Y-%m-%d}", f"{lunes + pd.Timedelta(days=1):%Y-%m-%d}"]
    # Alterar el miércoles en adelante de la semana objetivo no cambia nada.
    otro = cmg.copy()
    tarde = otro.fecha >= lunes + pd.Timedelta(days=2)
    otro.loc[tarde, xm.HORAS] = otro.loc[tarde, xm.HORAS] * 5
    pd.testing.assert_frame_equal(semanal.tabla_cmg(d, cmg).loc[[semana]], semanal.tabla_cmg(d, otro).loc[[semana]])
    # Sin el martes publicado, no hay candidato.
    sin_martes = cmg[cmg.fecha != lunes + pd.Timedelta(days=1)]
    assert pd.isna(semanal.tabla_cmg(d, sin_martes).at[semana, "cmg_2d_rel"])


def test_registro_antiguo_sin_columnas_de_candidato(tmp_path, monkeypatch):
    monkeypatch.setattr(semanal, "ARCHIVO", tmp_path / "pronosticos.csv")
    viejas = [c for c in semanal.COLUMNAS if not c.startswith("candidato")]
    fila = {c: None for c in viejas}
    fila.update(fecha_emision="2026-11-05", semana_base="2026-10-26", semana_objetivo="2026-11-02", pronostico=400.6)
    pd.DataFrame([fila])[viejas].to_csv(semanal.ARCHIVO, index=False)
    reg = semanal._leer_registro()
    assert list(reg.columns) == semanal.COLUMNAS and reg.candidato_pronostico.isna().all()
    reg.loc[0, "huella"] = "abc"  # una columna de texto vacía debe aceptar texto
    reg.loc[0, "cubierto"] = True


def test_completar_demanda_estima_solo_dias_incompletos():
    import data_pipeline as dp
    import xm_client as xm

    fechas = pd.date_range("2026-10-30", periods=3)
    demanda = pd.DataFrame({"fecha": fechas, "codigo": "Sistema", **{h: [10.0, 10.0, 2.5] for h in xm.HORAS}})
    gen = pd.DataFrame({"fecha": fechas, "codigo": "X", "valor": [240.0, 240.0, 240.0]})
    corregida, estimados = dp.completar_demanda(demanda, gen)
    assert list(estimados) == [fechas[2]]
    assert corregida[xm.HORAS].sum(axis=1).tolist() == pytest.approx([240.0, 240.0, 240.0])


def test_no_califica_con_demanda_estimada(tmp_path, monkeypatch, d):
    monkeypatch.setattr(semanal, "REGISTRO", tmp_path)
    monkeypatch.setattr(semanal, "ARCHIVO", tmp_path / "pronosticos.csv")
    semana = d.index[-3]
    semanal.registrar(_emision(semana, 90.0))
    tabla = d.assign(dias_demanda_estimada=0)
    tabla.loc[semana + pd.Timedelta(weeks=1), "dias_demanda_estimada"] = 1
    assert semanal.calificar(tabla).real.isna().all()
    assert semanal.calificar(d.assign(dias_demanda_estimada=0)).real.notna().all()


def test_huella_detecta_alteracion(tmp_path, monkeypatch, d):
    monkeypatch.setattr(semanal, "REGISTRO", tmp_path)
    monkeypatch.setattr(semanal, "ARCHIVO", tmp_path / "pronosticos.csv")
    semanal.registrar(_emision(d.index[-4], 90.0))
    semanal.registrar(_emision(d.index[-3], 95.0))
    assert semanal.verificar_registro() == []
    semanal.calificar(d)  # calificar no altera lo emitido
    assert semanal.verificar_registro() == []
    reg = semanal._leer_registro()
    reg.loc[0, "pronostico"] = 91.0
    semanal._escribir(reg)
    assert len(semanal.verificar_registro()) == 2  # la fila alterada y las que encadenan con ella


def test_embalse_bajo_pide_vigilancia(d):
    semana = d.index[-2]
    bajo = d.copy()
    bajo.loc[semana, "embalse_cierre"] = 0.40
    controles = monitoreo.calidad(bajo, semana, semana + pd.Timedelta(days=8))
    assert "Régimen de embalse bajo" in set(controles.control)
    assert monitoreo.estado(controles, pd.DataFrame(columns=["nivel"]), {"semanas": 0})[0] == "vigilancia"
