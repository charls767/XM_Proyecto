"""Gráficas de resultados para el README y el dashboard."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

import backtesting as bt  # noqa: E402


def frontera_e7(periodo="seleccion", exceso_max=100):
    """Cobertura en semanas de alta variabilidad frente al exceso medio de la cota.
    Omite los métodos con exceso mayor que `exceso_max` % (inestables)."""
    t = pd.read_csv(bt.RESULTADOS / "E7_resumen.csv", index_col=0)
    t = t[[c for c in t.columns if c.startswith(f"{periodo}:")]]
    t.columns = [c.split(":")[1] for c in t.columns]
    omitidos = t.index[t["exceso_medio_%"] > exceso_max].tolist()
    t = t.drop(omitidos)
    x, y = t["exceso_medio_%"], t.cobertura_alta_var * 100
    # Frontera de Pareto: ningún otro método cubre más las semanas volátiles con menos exceso.
    pareto = [n for n in t.index if not ((x <= x[n]) & (y >= y[n]) & ((x < x[n]) | (y > y[n]))).any()]
    fig, ax = plt.subplots(figsize=(11, 7))
    otros = t.index.difference(pareto)
    ax.scatter(x[otros], y[otros], color="#bdbdbd", s=35, label="otros métodos")
    puntos = ax.scatter(x[pareto], y[pareto], c=t.pinball[pareto], cmap="viridis_r", s=90,
                        edgecolor="black", linewidth=0.6, zorder=3)
    orden = x[pareto].sort_values().index
    ax.plot(x[orden], y[orden], color="black", lw=0.8, ls="--", zorder=2, label="frontera de Pareto")
    for nombre in list(pareto) + ["Ridge+conformal"]:
        ax.annotate(f"{nombre}\n(pinball {t.pinball[nombre]:.1f}, cob. {t.cobertura[nombre]:.0%})",
                    (x[nombre], y[nombre]), fontsize=8, xytext=(6, -4), textcoords="offset points",
                    fontweight="bold" if nombre == "Ridge+conformal" else "normal")
    ax.set_xlim(right=x.max() + 0.25 * (x.max() - x.min()))
    ax.legend(loc="lower right")
    ax.axhline(85, color="#c62828", ls=":", lw=1)
    ax.text(ax.get_xlim()[0], 85.5, "meta 85 % en semanas volátiles", color="#c62828", fontsize=8)
    ax.set_xlabel("Exceso medio de la cota sobre el precio real cuando cubre (%)")
    ax.set_ylabel("Cobertura en semanas de alta variabilidad (%)")
    ax.set_title(f"Frontera de compromiso de las cotas al 90 % ({periodo})")
    fig.colorbar(puntos, label="Pérdida pinball")
    if omitidos:
        fig.text(0.01, 0.01, "Omitidos por exceso > %d %%: %s" % (exceso_max, ", ".join(omitidos)), fontsize=7)
    fig.tight_layout()
    archivo = bt.RESULTADOS / f"E7_frontera_{periodo}.png"
    fig.savefig(archivo, dpi=130)
    return archivo
