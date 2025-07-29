# -*- coding: utf-8 -*-
import sys
import requests
import time
import matplotlib.pyplot as plt
import numpy as np

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QFormLayout, QMessageBox,
    QComboBox, QHBoxLayout, QFrame, QCheckBox, QScrollArea, QVBoxLayout
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

# Constantes
CASCADA_OFFSET_X = 30
CASCADA_OFFSET_Y = 30
SATOSHIS_POR_BTC = 100_000_000
BLOQUES_POR_DIA = 144
FACTOR_RENDIMIENTO_SOLAR = 0.8

MINEROS = {
    "S19":      {"ths": 95, "consumo": 3.250, "precio": 550},
    "S19K Pro": {"ths": 120, "consumo": 2.760, "precio": 770},
    "S21":      {"ths": 200, "consumo": 3.500, "precio": 2211},
    "S21 XP": {"ths": 270, "consumo": 3.645, "precio": 4850.62},
    "S23 Hyd":  {"ths": 580, "consumo": 5.510, "precio": 11311},
    "Fluminer T3": {"ths": 115, "consumo": 1.700, "precio": 1900},
    "Avalon Q": {"ths": 90, "consumo": 1.674, "precio": 1500},
    "Avalon Nano 3S": {"ths": 6, "consumo": 0.140, "precio": 290},
    "NerdMiner NerdQaxe++": {"ths": 4.8, "consumo": 0.072, "precio": 350},
    "NerdMiner NerdQaxe+ Hyd": {"ths": 2.5, "consumo": 0.060, "precio": 429},
    "Bitaxe Touch": {"ths": 1.6, "consumo": 0.022, "precio": 275},
    "Bitaxe Gamma 601": {"ths": 1.2, "consumo": 0.017, "precio": 58},
    "Bitaxe Gamma Turbo": {"ths": 2.5, "consumo": 0.036, "precio": 347},
    "Bitaxe Supra Hex 701": {"ths": 4.2, "consumo": 0.090, "precio": 235},

}

def obtener_cambio_usd_eur():
    """Obtiene el tipo de cambio USD/EUR desde la API de Frankfurter"""
    try:
        url = "https://api.frankfurter.app/latest?from=USD&to=EUR"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()  # Lanza excepción si hay error HTTP
        data = resp.json()
        return round(data["rates"]["EUR"], 4)
    except requests.RequestException as e:
        print(f"Error obteniendo cambio USD/EUR: {e}")
        return None
    except (KeyError, ValueError) as e:
        print(f"Error procesando datos de cambio: {e}")
        return None

def obtener_precio_btc():
    """Obtiene el precio actual de Bitcoin desde CoinGecko"""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return float(data["bitcoin"]["usd"])
    except requests.RequestException as e:
        print(f"Error obteniendo precio BTC: {e}")
        return None
    except (KeyError, ValueError) as e:
        print(f"Error procesando precio BTC: {e}")
        return None

def obtener_hashprice_directo():
    """Función simplificada - siempre retorna None para usar el cálculo manual"""
    return None

def obtener_hashprice_mempool_simple():
    """Función simplificada - siempre retorna None para usar el cálculo manual"""
    return None

def obtener_hashrate_eh():
    """Obtiene el hashrate actual de la red Bitcoin"""
    try:
        url = "https://mempool.space/api/v1/mining/hashrate/3d"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        hs = data["currentHashrate"]
        ehs = hs / 1e18
        return round(ehs, 2)
    except requests.RequestException as e:
        print(f"Error obteniendo hashrate: {e}")
        return None
    except (KeyError, ValueError) as e:
        print(f"Error procesando hashrate: {e}")
        return None

def estimar_fees_mempool(block_height, subsidio_btc=3.125):
    try:
        hash_url = f"https://mempool.space/api/block-height/{block_height}"
        block_hash = requests.get(hash_url, timeout=10).text.strip()
        txids_url = f"https://mempool.space/api/block/{block_hash}/txids"
        txids = requests.get(txids_url, timeout=10).json()
        coinbase_txid = txids[0]
        coinbase_url = f"https://mempool.space/api/tx/{coinbase_txid}"
        coinbase = requests.get(coinbase_url, timeout=10).json()
        recompensa_total = sum([vout["value"] for vout in coinbase["vout"]]) / 1e8
        fees = recompensa_total - subsidio_btc
        return fees
    except Exception as e:
        return None

def obtener_fees_btc_bloque_mempool(block_count=20, subsidio_btc=3.125):
    """
    Versión ultra-eficiente usando endpoint de estadísticas de mempool.space
    Una sola request para obtener datos de las últimas 24 horas
    Retorna (fees_promedio, numero_bloques_reales)
    """
    try:
        # Usar endpoint de estadísticas que da directamente las fees promedio
        url = "https://mempool.space/api/v1/mining/blocks/fees/24h"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code != 200:
            # Fallback a método tradicional si el endpoint no responde
            fees = obtener_fees_btc_bloque_tradicional(block_count, subsidio_btc)
            return (fees, BLOQUES_POR_DIA) if fees else (None, BLOQUES_POR_DIA)
            
        data = resp.json()
        
        if data and len(data) > 0:
            # Los datos vienen en satoshis en el campo 'avgFees'
            bloques_con_fees = [block for block in data if block.get('avgFees', 0) > 0]
            
            if bloques_con_fees:
                total_fees_sats = sum([block.get('avgFees', 0) for block in bloques_con_fees])
                numero_bloques_reales = len(bloques_con_fees)
                avg_fees_sats = total_fees_sats / numero_bloques_reales
                avg_fees_btc = avg_fees_sats / 1e8  # Convertir de sats a BTC
                
                return (round(avg_fees_btc, 6), numero_bloques_reales)
            
        # Fallback a método tradicional si no hay datos válidos
        fees = obtener_fees_btc_bloque_tradicional(block_count, subsidio_btc)
        return (fees, BLOQUES_POR_DIA) if fees else (None, BLOQUES_POR_DIA)
        
    except Exception as e:
        print(f"Error en endpoint optimizado: {e}")
        # Fallback a método tradicional en caso de error
        fees = obtener_fees_btc_bloque_tradicional(block_count, subsidio_btc)
        return (fees, BLOQUES_POR_DIA) if fees else (None, BLOQUES_POR_DIA)

def obtener_fees_btc_bloque_tradicional(block_count=20, subsidio_btc=3.125):
    """
    Método tradicional como backup
    """
    try:
        bloques = requests.get("https://mempool.space/api/blocks", timeout=10).json()
        if not bloques:
            return None
        total_fees = 0
        bloques_ok = 0
        for bloque in bloques[:block_count]:
            height = bloque["height"]
            fees = estimar_fees_mempool(height, subsidio_btc)
            if fees is not None:
                total_fees += fees
                bloques_ok += 1
            time.sleep(0.2)
        if bloques_ok == 0:
            return None
        media_fee_btc = total_fees / bloques_ok
        return round(media_fee_btc, 6)
    except Exception as e:
        return None

class VentanaResultados(QWidget):
    def __init__(self, resultado_html, nombre_minero, ventana_principal=None, offset_cascada=0):
        super().__init__()
        self.setWindowTitle(f"📊 Resultados - {nombre_minero}")
        
        # Calcular posición relativa a la ventana principal con efecto cascada
        if ventana_principal:
            # Obtener geometría de la ventana principal
            geo_principal = ventana_principal.geometry()
            x_principal = geo_principal.x()
            y_principal = geo_principal.y()
            ancho_principal = geo_principal.width()
            
            # Posicionar a la derecha de la ventana principal con un margen
            # Aplicar offset de cascada usando constantes
            x_nueva = x_principal + ancho_principal + 20 + (offset_cascada * CASCADA_OFFSET_X)
            y_nueva = y_principal + (offset_cascada * CASCADA_OFFSET_Y)
            
            self.setGeometry(x_nueva, y_nueva, 800, 600)
        else:
            # Fallback si no hay ventana principal, también con cascada
            x_nueva = 100 + (offset_cascada * CASCADA_OFFSET_X)
            y_nueva = 100 + (offset_cascada * CASCADA_OFFSET_Y)
            self.setGeometry(x_nueva, y_nueva, 800, 600)
            
        self.init_ui(resultado_html)
        
    def init_ui(self, resultado_html):
        layout = QVBoxLayout()
        
        # Etiqueta de resultado con scroll
        self.resultado = QLabel(resultado_html)
        self.resultado.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.resultado.setWordWrap(True)
        
        # Configurar fuente con soporte de emojis solo para los resultados
        emoji_font = QFont()
        emoji_font.setPointSize(13)
        emoji_font.setStyleHint(QFont.System)  # Usar fuente del sistema
        self.resultado.setFont(emoji_font)
        self.resultado.setStyleSheet("margin-left: 10px; font-size: 13px; font-family: system-ui, -apple-system, 'Segoe UI', sans-serif;")
        
        # Área de scroll
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.resultado)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #f8f8f8; 
                border: 1px solid #ccc;
            }
            QScrollArea > QWidget > QWidget {
                background-color: #f8f8f8;
            }
            QScrollBar:vertical {
                background-color: #d0d0d0;
                width: 14px;
                border: none;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background-color: #909090;
                border-radius: 7px;
                min-height: 30px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #707070;
            }
            QScrollBar::handle:vertical:pressed {
                background-color: #505050;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        layout.addWidget(scroll_area)
        self.setLayout(layout)

class CalculadoraMineria(QWidget):

    def _crear_campo_con_boton(self, widget, boton):
        layout = QHBoxLayout()
        layout.addWidget(widget)
        layout.addSpacing(8)
        layout.addWidget(boton)
        layout.setSpacing(2)
        layout.setContentsMargins(0, 0, 0, 0)
        return layout


    def mostrar_grafica_amortizacion(self, beneficio_anual, inversion, nombre_minero, ventana_resultados=None, offset_cascada=0):
        anios = np.arange(0, 11)  # De 0 a 10 años
        beneficio_acumulado = beneficio_anual * anios

        fig = plt.figure(figsize=(8, 5))
        fig.canvas.manager.set_window_title(f"📈 Amortización - {nombre_minero}")
        
        plt.plot(anios, beneficio_acumulado, label="Beneficio acumulado", marker='o')
        plt.axhline(inversion, color='red', linestyle='--', label="Inversión inicial")
        plt.xlabel("Años")
        plt.ylabel("€")
        plt.title("Punto de amortización")
        plt.legend()
        plt.grid(True)

        # Marcar el punto de amortización si es posible
        if beneficio_anual > 0:
            x_amort = inversion / beneficio_anual
            if x_amort <= anios[-1]:
                plt.axvline(x_amort, color='green', linestyle=':', label=f"Amortización: {x_amort:.2f} años")
                plt.legend()

        plt.tight_layout()
        plt.show()
        
        # Guardar referencia a la figura para poder cerrarla después
        self.figuras_matplotlib.append(fig)
        
        # Posicionar la ventana de la gráfica debajo de la ventana de resultados
        # con el mismo margen que hay entre la ventana principal y la de resultados (20px)
        # Esto debe hacerse después de plt.show() para que la ventana esté disponible
        if ventana_resultados:
            try:
                geo_resultados = ventana_resultados.geometry()
                x_resultados = geo_resultados.x()
                y_resultados = geo_resultados.y()
                alto_resultados = geo_resultados.height()
                
                # Posicionar debajo de la ventana de resultados con el mismo margen (20px)
                # que se usa entre la ventana principal y la de resultados
                x_grafica = x_resultados
                y_grafica = y_resultados + alto_resultados + 20
                
                # Mover la ventana de matplotlib usando diferentes métodos según el backend
                mngr = fig.canvas.manager
                if hasattr(mngr, 'window'):
                    if hasattr(mngr.window, 'wm_geometry'):
                        # Para backends como TkAgg
                        mngr.window.wm_geometry(f"+{x_grafica}+{y_grafica}")
                    elif hasattr(mngr.window, 'move'):
                        # Para backends como Qt5Agg
                        mngr.window.move(x_grafica, y_grafica)
                    elif hasattr(mngr.window, 'setGeometry'):
                        # Para backends como Qt5Agg alternativo
                        mngr.window.setGeometry(x_grafica, y_grafica, 640, 480)
            except Exception as e:
                # Si falla el posicionamiento, no pasa nada, la gráfica se muestra normalmente
                print(f"No se pudo posicionar la ventana de gráfica: {e}")


    def init_ui(self):
        layout = QFormLayout()
        layout.setSpacing(10)

        # ------ SECCIÓN: DATOS DE LA RED ------
        titulo_red = QLabel("<b>🌍 Red BTC</b>")
        titulo_red.setAlignment(Qt.AlignCenter)
        titulo_red.setTextInteractionFlags(Qt.TextSelectableByMouse)
        
        self.boton_actualizar_todo = QPushButton("🔄 Datos")
        self.boton_actualizar_todo.clicked.connect(self.actualizar_todos_los_campos)
        
        hbox_red_titulo = QHBoxLayout()
        hbox_red_titulo.addStretch(1)
        hbox_red_titulo.addWidget(titulo_red)
        hbox_red_titulo.addWidget(self.boton_actualizar_todo)
        hbox_red_titulo.addStretch(1)
        contenedor_red_titulo = QWidget()
        contenedor_red_titulo.setLayout(hbox_red_titulo)
        layout.addRow(contenedor_red_titulo)

        # Campos de entrada SIN botones de actualizar ni calcular, etiquetas seleccionables
        label_cambio = QLabel("💶 Cambio EUR/USD:")
        label_cambio.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.cambio_usd_eur = QLineEdit()
        layout.addRow(label_cambio, self.cambio_usd_eur)

        label_btc = QLabel("₿ Precio BTC (USD):")
        label_btc.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.precio_btc = QLineEdit()
        layout.addRow(label_btc, self.precio_btc)
        self.precio_btc.textChanged.connect(self.actualizar_hashprice_spot)

        label_hashrate = QLabel("🌐 Hashrate red (EH/s):")
        label_hashrate.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.hashrate_eh = QLineEdit()
        self.hashrate_eh.textChanged.connect(self.actualizar_hashprice_spot)
        layout.addRow(label_hashrate, self.hashrate_eh)

        label_fees = QLabel("🪙 Fees últimas 24h (BTC):")
        label_fees.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.fees_btc_bloque = QLineEdit()
        layout.addRow(label_fees, self.fees_btc_bloque)
        self.fees_btc_bloque.textChanged.connect(self.actualizar_hashprice_spot)

        label_hashprice = QLabel("💹 Hashprice (spot) (USD/PH/día):")
        label_hashprice.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.hashprice_spot = QLineEdit()
        layout.addRow(label_hashprice, self.hashprice_spot)

        label_recompensa = QLabel("🎁 Recompensa por bloque (BTC):")
        label_recompensa.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.recompensa_btc = QLineEdit("3.125")
        layout.addRow(label_recompensa, self.recompensa_btc)
        # Actualizar hashprice y resultados al cambiar la recompensa
        self.recompensa_btc.textChanged.connect(self.actualizar_hashprice_spot)

        label_comision = QLabel("🏦 Fees pool (2%):")
        label_comision.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.comision = QLineEdit("0.02")
        layout.addRow(label_comision, self.comision)

        # ...el resto del código de la interfaz...

        separador1 = QFrame()
        separador1.setFrameShape(QFrame.HLine)
        separador1.setFrameShadow(QFrame.Sunken)
        layout.addRow(separador1)

        # ------ DESPLEGABLE DEL MINERO Y SUS DATOS ------
        titulo_minero = QLabel("<b>🔨 Mineros</b>")
        titulo_minero.setAlignment(Qt.AlignCenter)
        titulo_minero.setTextInteractionFlags(Qt.TextSelectableByMouse)
        
        self.combo_minero = QComboBox()
        self.combo_minero.addItem("Selecciona un modelo")
        for modelo in MINEROS:
            self.combo_minero.addItem(modelo)
        self.combo_minero.addItem("Otro")
        self.combo_minero.currentIndexChanged.connect(self.autocompletar_minero)

        
        hbox_minero_titulo = QHBoxLayout()
        hbox_minero_titulo.addStretch(1)
        hbox_minero_titulo.addWidget(titulo_minero)
        hbox_minero_titulo.addWidget(self.combo_minero)
        hbox_minero_titulo.addStretch(1)
        contenedor_minero_titulo = QWidget()
        contenedor_minero_titulo.setLayout(hbox_minero_titulo)
        layout.addRow(contenedor_minero_titulo)

        label_num_minero = QLabel("📟 Numero de máquinas:")
        label_num_minero.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.num_minero = QComboBox()
        for i in range(1, 11):
            self.num_minero.addItem(str(i))
        self.num_minero.setCurrentIndex(0)  # Seleccionar "1" por defecto
        layout.addRow(label_num_minero, self.num_minero)

        label_ths = QLabel("🚀 Hashrate equipo (TH/s):")
        label_ths.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.ths = QLineEdit("100")
        layout.addRow(label_ths, self.ths)

        label_consumo = QLabel("🔋 Potencia eléctrica (kW):")
        label_consumo.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.consumo_kw = QLineEdit("3.5")
        layout.addRow(label_consumo, self.consumo_kw)

        label_precio_equipo = QLabel("💶 Precio equipo (€):")
        label_precio_equipo.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.precio_equipo = QLineEdit("500")
        layout.addRow(label_precio_equipo, self.precio_equipo)


        separador2 = QFrame()
        separador2.setFrameShape(QFrame.HLine)
        separador2.setFrameShadow(QFrame.Sunken)
        layout.addRow(separador2)

        # ------ TÍTULO SOLAR CON CHECKBOX ------
        self.chk_solar = QCheckBox()
        self.chk_solar.setChecked(True)
        self.chk_solar.stateChanged.connect(self.toggle_solar_fields)
        
        titulo_solar = QLabel("<b>🌞 Instalación solar</b>")
        titulo_solar.setAlignment(Qt.AlignCenter)
        titulo_solar.setTextInteractionFlags(Qt.TextSelectableByMouse)
        
        hbox_solar = QHBoxLayout()
        hbox_solar.addStretch(1)
        hbox_solar.addWidget(titulo_solar)
        hbox_solar.addWidget(self.chk_solar)
        hbox_solar.addStretch(1)
        contenedor_solar = QWidget()
        contenedor_solar.setLayout(hbox_solar)
        layout.addRow(contenedor_solar)

        label_precio_venta = QLabel("💸 Excedente no vendido (€/kWh):")
        label_precio_venta.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.precio_venta_solar = QLineEdit("0.04")
        layout.addRow(label_precio_venta, self.precio_venta_solar)

        label_horas_solares = QLabel("🌤️ Horas solares/día:")
        label_horas_solares.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.horas_solares_dia = QLineEdit("5.5")
        layout.addRow(label_horas_solares, self.horas_solares_dia)

        label_dias_uso = QLabel("📅 Días de uso/año:")
        label_dias_uso.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.dias_uso = QLineEdit("365")
        layout.addRow(label_dias_uso, self.dias_uso)


        self.solar_widgets = [self.precio_venta_solar, self.horas_solares_dia, self.dias_uso]

        separador2 = QFrame()
        separador2.setFrameShape(QFrame.HLine)
        separador2.setFrameShadow(QFrame.Sunken)
        layout.addRow(separador2)

        # ------ TÍTULO RED ELÉCTRICA CON CHECKBOX ------
        self.chk_red = QCheckBox()
        self.chk_red.setChecked(True)
        self.chk_red.stateChanged.connect(self.toggle_red_fields)
        
        titulo_red_elec = QLabel("<b>🏭 Conexión a red eléctrica</b>")
        titulo_red_elec.setAlignment(Qt.AlignCenter)
        titulo_red_elec.setTextInteractionFlags(Qt.TextSelectableByMouse)
        
        hbox_red = QHBoxLayout()
        hbox_red.addStretch(1)
        hbox_red.addWidget(titulo_red_elec)
        hbox_red.addWidget(self.chk_red)
        hbox_red.addStretch(1)
        contenedor_red = QWidget()
        contenedor_red.setLayout(hbox_red)
        layout.addRow(contenedor_red)

        label_precio_red = QLabel("💡 Electricidad (€/kWh):")
        label_precio_red.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.precio_red = QLineEdit("0.08")
        layout.addRow(label_precio_red, self.precio_red)

        label_horas_red = QLabel("🔌 Horas de uso/día:")
        label_horas_red.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.horas_red_dia = QLineEdit("8")
        layout.addRow(label_horas_red, self.horas_red_dia)

        label_dias_red = QLabel("📅 Días de uso/año:")
        label_dias_red.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.dias_red = QLineEdit("365")
        layout.addRow(label_dias_red, self.dias_red)


        self.red_widgets = [self.precio_red, self.horas_red_dia, self.dias_red]

        layout.addRow(QLabel(""))

        self.boton = QPushButton("🧮 Calcular")
        self.boton.setDefault(True)
        self.boton.clicked.connect(self.calcular)

        self.boton_cerrar_ventanas = QPushButton("🗑️ Cerrar ventanas")
        self.boton_cerrar_ventanas.clicked.connect(self.cerrar_todas_ventanas)

        hbox_boton = QHBoxLayout()
        hbox_boton.addStretch(1)
        hbox_boton.addWidget(self.boton)
        hbox_boton.addSpacing(10)
        hbox_boton.addWidget(self.boton_cerrar_ventanas)
        hbox_boton.addStretch(1)
        contenedor_boton = QWidget()
        contenedor_boton.setLayout(hbox_boton)
        layout.addRow(contenedor_boton)

        self.setLayout(layout)

    def calcular(self):
        # Siempre toma los valores actuales de la interfaz y actualiza los resultados
        # Validar datos antes de proceder
        if not self.validar_datos_entrada():
            QMessageBox.critical(self, "Error", "Por favor, revisa que todos los campos contengan valores numéricos válidos.")
            return
        # ...el resto del código de calcular() permanece igual...

        # ...código eliminado: creación duplicada de botones y layouts...

    def __init__(self):
        super().__init__()
        self.setWindowTitle("☀️ Calculadora de Minería Solar")
        self.setGeometry(100, 100, 400, 800)  # x, y, ancho, alto
        self.ventanas_resultados = []  # Lista para mantener referencias a ventanas abiertas
        self.figuras_matplotlib = []  # Lista para mantener referencias a figuras de matplotlib
        self.bloques_reales_24h = BLOQUES_POR_DIA  # Número real de bloques en 24h
        self.init_ui()

    def limpiar_ventanas_cerradas(self):
        """Elimina de la lista las ventanas que han sido cerradas"""
        self.ventanas_resultados = [ventana for ventana in self.ventanas_resultados if ventana.isVisible()]

    def limpiar_figuras_cerradas(self):
        """Elimina de la lista las figuras de matplotlib que han sido cerradas"""
        import matplotlib.pyplot as plt
        figuras_abiertas = plt.get_fignums()
        self.figuras_matplotlib = [fig for fig in self.figuras_matplotlib if fig.number in figuras_abiertas]

    def cerrar_todas_ventanas(self):
        """Cierra todas las ventanas de resultados y gráficas abiertas"""
        # Cerrar ventanas de resultados
        for ventana in self.ventanas_resultados:
            if ventana.isVisible():
                ventana.close()
        self.ventanas_resultados.clear()
        
        # Cerrar figuras de matplotlib
        import matplotlib.pyplot as plt
        for figura in self.figuras_matplotlib:
            try:
                plt.close(figura)
            except:
                pass  # La figura ya podría estar cerrada
        self.figuras_matplotlib.clear()

    def closeEvent(self, event):
        """Se ejecuta cuando se cierra la ventana principal"""
        self.cerrar_todas_ventanas()
        super().closeEvent(event)

    def toggle_solar_fields(self):
        enabled = self.chk_solar.isChecked()
        for w in self.solar_widgets:
            w.setEnabled(enabled)

    def actualizar_hashprice_spot(self):
        try:
            precio_btc = float(self.precio_btc.text())
            recompensa_btc = float(self.recompensa_btc.text())
            
            # Campo de fees ahora contiene solo el valor numérico
            fees_btc_bloque = float(self.fees_btc_bloque.text())
                
            hashrate_eh = float(self.hashrate_eh.text())

            # Cálculo estándar del hashprice usando 144 bloques teóricos:
            # Ingresos por bloque (recompensa + fees) en USD
            ingreso_usd_por_bloque = (recompensa_btc + fees_btc_bloque) * precio_btc
            
            # Hashrate en PH/s (1 EH = 1,000 PH)
            hashrate_ph = hashrate_eh * 1_000
            
            # Hashprice = Ingresos por bloque * 144 bloques teóricos / Hashrate en PH
            # Esto da USD por PH por día según el estándar de la industria
            hashprice_usd_ph_dia = (ingreso_usd_por_bloque * BLOQUES_POR_DIA) / hashrate_ph
            
            # Mostrar resultado en USD/PH/día
            self.hashprice_spot.setText(f"{hashprice_usd_ph_dia:.2f}")
        except Exception:
            self.hashprice_spot.setText("")

    def actualizar_todos_los_campos(self):
        QTimer.singleShot(0, self.actualizar_cambio)
        QTimer.singleShot(200, self.actualizar_precio_btc) 
        QTimer.singleShot(400, self.actualizar_hashrate)
        QTimer.singleShot(600, self.actualizar_fees_btc_bloque)
        QTimer.singleShot(800, self.actualizar_hashprice_spot)  

    def toggle_red_fields(self):
        enabled = self.chk_red.isChecked()
        for w in self.red_widgets:
            w.setEnabled(enabled)

    def autocompletar_minero(self):
        modelo = self.combo_minero.currentText()
        if modelo in MINEROS:
            datos = MINEROS[modelo]
            self.ths.setText(str(datos["ths"]))
            self.consumo_kw.setText(str(datos["consumo"]))
            self.precio_equipo.setText(str(datos["precio"]))
        elif modelo == "Otro":
            self.ths.setText("")
            self.consumo_kw.setText("")
            self.precio_equipo.setText("")

    def actualizar_cambio(self):
        cambio = obtener_cambio_usd_eur()
        if cambio:
            self.cambio_usd_eur.setText(str(cambio))
        else:
            QMessageBox.warning(self, "Error", "No se pudo obtener el cambio USD/EUR.")

    def actualizar_precio_btc(self):
        precio = obtener_precio_btc()
        if precio:
            self.precio_btc.setText(str(precio))
        else:
            QMessageBox.warning(self, "Error", "No se pudo obtener el precio de BTC.")

    def actualizar_hashrate(self):
        hashrate = obtener_hashrate_eh()
        if hashrate:
            self.hashrate_eh.setText(str(hashrate))
        else:
            QMessageBox.warning(self, "Error", "No se pudo obtener el hashrate de la red.")

    def actualizar_fees_btc_bloque(self):
        resultado = obtener_fees_btc_bloque_mempool()
        if resultado and resultado[0] is not None:
            fee, bloques_reales = resultado
            self.bloques_reales_24h = bloques_reales  # Actualizar el número real de bloques
            # Mostrar solo la fee sin información de bloques
            self.fees_btc_bloque.setText(f"{fee:.3f}")
            # Actualizar también el hashprice con los datos reales
            self.actualizar_hashprice_spot()
        else:
            QMessageBox.warning(self, "Error", "No se pudo obtener la media de fees por bloque.")

    def validar_datos_entrada(self):
        """Valida que todos los campos obligatorios tengan valores válidos"""
        try:
            # Validar datos de red
            float(self.precio_btc.text())
            float(self.cambio_usd_eur.text())
            float(self.hashrate_eh.text())
            
            # Validar fees (formato simple sin paréntesis)
            fees_text = self.fees_btc_bloque.text()
            float(fees_text)
            
            float(self.hashprice_spot.text())
            float(self.recompensa_btc.text())
            float(self.comision.text())
            
            # Validar datos del minero
            int(self.num_minero.currentText())
            float(self.ths.text())
            float(self.consumo_kw.text())
            float(self.precio_equipo.text())
            
            # Validar datos solares si están activados
            if self.chk_solar.isChecked():
                float(self.precio_venta_solar.text())
                float(self.horas_solares_dia.text())
                int(self.dias_uso.text())
            
            # Validar datos de red eléctrica si están activados
            if self.chk_red.isChecked():
                float(self.precio_red.text())
                float(self.horas_red_dia.text())
                int(self.dias_red.text())
            
            return True
        except (ValueError, TypeError):
            return False

    def calcular(self):
        # Actualizar hashprice spot con los valores actuales antes de calcular
        self.actualizar_hashprice_spot()
        # Validar datos antes de proceder
        if not self.validar_datos_entrada():
            QMessageBox.critical(self, "Error", "Por favor, revisa que todos los campos contengan valores numéricos válidos.")
            return
        try:
            precio_btc = float(self.precio_btc.text())
            cambio_usd_eur = float(self.cambio_usd_eur.text())
            num_minero = int(self.num_minero.currentText())
            ths = float(self.ths.text()) * num_minero
            consumo_kw = float(self.consumo_kw.text()) * num_minero
            precio_equipo = float(self.precio_equipo.text()) * num_minero
            comision = float(self.comision.text())

            # Hashprice en EUR/TH/día (desde campo hashprice_spot en USD/PH/día)
            hashprice_usd_ph_dia = float(self.hashprice_spot.text())  # USD/PH/día
            hashprice_usd_th_dia = hashprice_usd_ph_dia / 1000  # USD/TH/día (1 PH = 1000 TH)
            hashprice_eur_th_dia = hashprice_usd_th_dia * cambio_usd_eur

            # Solar activado o no
            solar_activado = self.chk_solar.isChecked()
            if solar_activado:
                horas_solares_dia = float(self.horas_solares_dia.text())
                dias_uso = int(self.dias_uso.text())
                precio_venta_solar = float(self.precio_venta_solar.text())
                horas_solares_anuales = horas_solares_dia * dias_uso
                # Ingreso solar bruto y neto
                ingreso_solar_bruto_anual = hashprice_eur_th_dia * ths * (horas_solares_anuales / 24)
                ingreso_solar_neto_anual = ingreso_solar_bruto_anual * (1 - comision)
                energia_consumida_kwh = consumo_kw * horas_solares_anuales
                valor_no_recibido = energia_consumida_kwh * precio_venta_solar
                produccion_anual = ingreso_solar_neto_anual - valor_no_recibido
                produccion_bruta_anual = ingreso_solar_bruto_anual  # CORREGIDO: ingreso bruto sin descontar valor_no_recibido
                # Tabla solar
                produccion_tabla_solar = ingreso_solar_bruto_anual  # SIN fees
                fees_tabla_solar = ingreso_solar_bruto_anual * comision  # Fees del pool
                coste_tabla_solar = -valor_no_recibido
                beneficio_tabla_solar = produccion_anual
            else:
                horas_solares_anuales = 0
                produccion_bruta_anual = 0
                energia_consumida_kwh = 0
                valor_no_recibido = 0
                produccion_anual = 0
                precio_venta_solar = 0
                produccion_tabla_solar = 0
                fees_tabla_solar = 0
                coste_tabla_solar = 0
                beneficio_tabla_solar = 0

            red_activada = self.chk_red.isChecked()
            if red_activada:
                precio_red = float(self.precio_red.text())
                horas_red_anuales = float(self.horas_red_dia.text()) * int(self.dias_red.text())
                # Ingreso red bruto y neto
                ingreso_red_bruto_anual = hashprice_eur_th_dia * ths * (horas_red_anuales / 24)
                ingreso_red_neto_anual = ingreso_red_bruto_anual * (1 - comision)
                consumo_red_anual = consumo_kw * horas_red_anuales
                coste_red_anual = consumo_red_anual * precio_red
                produccion_red_neta = ingreso_red_neto_anual - coste_red_anual
                produccion_red_bruta = ingreso_red_bruto_anual  # CORREGIDO: ingreso bruto sin descontar coste_red_anual
                # Tabla red
                produccion_tabla_red = ingreso_red_bruto_anual  # SIN fees
                fees_tabla_red = ingreso_red_bruto_anual * comision  # Fees del pool
                coste_tabla_red = -coste_red_anual
                beneficio_tabla_red = produccion_red_neta
            else:
                precio_red = 0
                horas_red_anuales = 0
                consumo_red_anual = 0
                coste_red_anual = 0
                produccion_red_neta = 0
                produccion_red_bruta = 0
                produccion_tabla_red = 0
                fees_tabla_red = 0
                coste_tabla_red = 0
                beneficio_tabla_red = 0

            # Rentabilidades - CORREGIDAS
            # Para solar: rentabilidad bruta = ingresos brutos / consumo
            euros_por_kwh_bruto = produccion_bruta_anual / energia_consumida_kwh if energia_consumida_kwh else 0

            # Para solar: rentabilidad neta = beneficio neto / consumo
            euros_por_kwh = beneficio_tabla_solar / energia_consumida_kwh if energia_consumida_kwh else 0

            # Para red: rentabilidad bruta = ingresos brutos / consumo
            euros_por_kwh_red_bruto = produccion_red_bruta / consumo_red_anual if consumo_red_anual else 0
            # Para red: rentabilidad neta = beneficio neto / consumo
            euros_por_kwh_red = produccion_red_neta / consumo_red_anual if consumo_red_anual else 0

            potencia_fotovoltaica_kwp = (consumo_kw / FACTOR_RENDIMIENTO_SOLAR if FACTOR_RENDIMIENTO_SOLAR else 0) if solar_activado else 0

            eficiencia_w_th = (consumo_kw * 1000) / ths if ths > 0 else 0

            # Rentabilidades combinadas
            # Bruta: suma de ingresos brutos (antes de restar fees y costes) dividido entre el consumo total
            # Neta: suma de beneficios netos (después de restar fees y costes) dividido entre el consumo total
            rentabilidad_bruta_combinada = ((produccion_bruta_anual + produccion_red_bruta) / (energia_consumida_kwh + consumo_red_anual) if (energia_consumida_kwh + consumo_red_anual) > 0 else 0)
            rentabilidad_neta_combinada = ((beneficio_tabla_solar + beneficio_tabla_red) / (energia_consumida_kwh + consumo_red_anual) if (energia_consumida_kwh + consumo_red_anual) > 0 else 0)

            amortizacion = precio_equipo / beneficio_tabla_solar if beneficio_tabla_solar > 0 else 0
            amortizacion_red = precio_equipo / beneficio_tabla_red if red_activada and beneficio_tabla_red > 0 else 0
            produccion_total = beneficio_tabla_solar + (beneficio_tabla_red if red_activada else 0)
            amortizacion_total = precio_equipo / produccion_total if produccion_total > 0 else 0
            beneficio_10_anios = produccion_total * 10 - precio_equipo


            resultado = (
                f"<br>"
                # DATOS DEL MINERO
                f"<div style='text-align:center;'><b>🔨 DATOS DEL MINERO</b></div><br>"
                f"<div style='text-align:center;'>"
                f"<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse; text-align:center; margin:0 auto;'>"
                f"<tr><td>💻 <b>Modelo</b></td><td><b>{self.combo_minero.currentText()}</b></td></tr>"
                f"<tr><td>📟 <b>Máquinas</b></td><td>{num_minero}</td></tr>"
                f"<tr><td>🚀 <b>Hashrate</b></td><td>{ths:.1f} TH/s</td></tr>"
                f"<tr><td>🪫 <b>Potencia</b></td><td>{consumo_kw:.3f} kW</td></tr>"
                f"<tr><td>✨ <b>Eficiencia energética</b></td><td>{eficiencia_w_th:.2f} W/TH</td></tr>"
                f"<tr><td>💎 <b>Coste por terahash</b></td><td>{precio_equipo/ths:.2f} €/TH</td></tr>"
                f"<tr><td>💶 <b>Inversión en equipos</b></td><td>{precio_equipo:.2f} €</td></tr>"
                f"</table>"
                f"</div>"
                f"<br>"
                f"<hr>"
                f"<br>"
                # AMORTIZACIÓN
                f"<div style='text-align:center;'><b>💰 BENEFICIOS</b></div><br>"
                f"<div style='text-align:center;'>"
                f"<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse; text-align:center; margin:0 auto;'>"
                f"<tr><td style='background:white;'>🌞 <b>Amortización solar</b></td><td style='background:{'white' if not solar_activado else ('#ffcccc' if amortizacion <= 0 else '#e8f5e8')};'>{'-' if solar_activado and amortizacion == 0 else ''}{amortizacion:.2f} años</td></tr>"
                f"<tr><td style='background:white;'>🏭 <b>Amortización red</b></td><td style='background:{'white' if not red_activada else ('#ffcccc' if amortizacion_red <= 0 else '#e8f5e8')};'>{'-' if red_activada and amortizacion_red == 0 else ''}{amortizacion_red:.2f} años</td></tr>"
                f"<tr><td style='background:white;'>🔄 <b>Amortización combinada</b></td><td style='background:{'white' if not solar_activado and not red_activada else ('#ffcccc' if amortizacion_total <= 0 else '#e8f5e8')};'>{'-' if (solar_activado or red_activada) and amortizacion_total == 0 else ''}{amortizacion_total:.2f} años</td></tr>"
                f"<tr><td style='background:white;'>🖐 <b>Beneficio neto en 5 años</b></td><td style='background:{'white' if (produccion_total * 5 - precio_equipo) == 0 else ('#ffcccc' if (produccion_total * 5 - precio_equipo) < 0 else '#e8f5e8')};'>{(produccion_total * 5 - precio_equipo):.2f} €</td></tr>"
                f"<tr><td style='background:white;'>🙌 <b>Beneficio neto en 10 años</b></td><td style='background:{'white' if beneficio_10_anios == 0 else ('#ffcccc' if beneficio_10_anios < 0 else '#e8f5e8')};'>{beneficio_10_anios:.2f} €</td></tr>"
                f"</table>"
                f"</div>"
                f"<br>"
                f"<hr>"
                f"<br>"
                # SOLAR
                f"<div style='text-align:center;'><b>🌞 PRODUCCIÓN SOLAR</b></div><br>"
                f"<div style='text-align:center;'>"
                f"<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse; text-align:center; margin:0 auto;'>"
                f"<tr style='background:#f5f5f5;'><th></th><th>DÍA</th><th>MES</th><th>AÑO</th></tr>"
                f"<tr><td><b>💶 Producción</b></td>"
                f"<td>{produccion_tabla_solar/365:.2f} €</td>"
                f"<td>{produccion_tabla_solar/12:.2f} €</td>"
                f"<td>{produccion_tabla_solar:.2f} €</td></tr>"
                f"<tr><td><b>💸 Excedente no vendido</b></td>"
                f"<td>{coste_tabla_solar/365:.2f} €</td>"
                f"<td>{coste_tabla_solar/12:.2f} €</td>"
                f"<td>{coste_tabla_solar:.2f} €</td></tr>"
                f"<tr><td><b>🏦 Fees pool ({comision*100:.1f}%)</b></td>"
                f"<td>-{fees_tabla_solar/365:.3f} €</td>"
                f"<td>-{fees_tabla_solar/12:.3f} €</td>"
                f"<td>-{fees_tabla_solar:.3f} €</td></tr>"
                f"<tr><td style='background:white;'><b>{'❌' if beneficio_tabla_solar < 0 else '✅'} Beneficio neto</b></td>"
                f"<td style='background:{'white' if not solar_activado else ('white' if beneficio_tabla_solar == 0 else ('#ffcccc' if beneficio_tabla_solar < 0 else '#e8f5e8'))};'><b>{beneficio_tabla_solar/365:.2f} €</b></td>"
                f"<td style='background:{'white' if not solar_activado else ('white' if beneficio_tabla_solar == 0 else ('#ffcccc' if beneficio_tabla_solar < 0 else '#e8f5e8'))};'><b>{beneficio_tabla_solar/12:.2f} €</b></td>"
                f"<td style='background:{'white' if not solar_activado else ('white' if beneficio_tabla_solar == 0 else ('#ffcccc' if beneficio_tabla_solar < 0 else '#e8f5e8'))};'><b>{beneficio_tabla_solar:.2f} €</b></td></tr>"
                f"</table>"
                f"</div>"
                f"<br>"
                f"<br>"
                f"<div style='text-align:center;'>"
                f"<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse; text-align:center; margin:0 auto;'>"
                f"<tr><td>🔆 <b>Potencia fotovoltaica</b></td><td>{potencia_fotovoltaica_kwp:.2f} kWp</td></tr>"
                f"<tr><td>🪫 <b>Consumo anual</b></td><td>{energia_consumida_kwh:.1f} kWh</td></tr>"
                f"<tr><td>📈 <b>Rentabilidad bruta kWh</b></td><td style='background:{'white' if not solar_activado else ('white' if euros_por_kwh_bruto == 0 else ('#ffcccc' if euros_por_kwh_bruto < 0 else '#e8f5e8'))};'>{euros_por_kwh_bruto:.3f} €/kWh</td></tr>"
                f"<tr><td>📉 <b>Rentabilidad neta kWh</b></td><td style='background:{'white' if not solar_activado else ('white' if euros_por_kwh == 0 else ('#ffcccc' if euros_por_kwh < 0 else '#e8f5e8'))};'>{euros_por_kwh:.3f} €/kWh</td></tr>"
                f"</table>"
                f"</div>"
                f"<br>"
                f"<hr>"
                f"<br>"
                # ELÉCTRICA
                f"<div style='text-align:center;'><b>🏭 PRODUCCIÓN ELÉCTRICA</b></div><br>"
                f"<div style='text-align:center;'>"
                f"<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse; text-align:center; margin:0 auto;'>"
                f"<tr style='background:#f5f5f5;'><th></th><th>DÍA</th><th>MES</th><th>AÑO</th></tr>"
                f"<tr><td><b>💶 Producción</b></td>"
                f"<td>{produccion_tabla_red/365:.2f} €</td>"
                f"<td>{produccion_tabla_red/12:.2f} €</td>"
                f"<td>{produccion_tabla_red:.2f} €</td></tr>"
                f"<tr><td><b>💡 Electricidad</b></td>"
                f"<td>{coste_tabla_red/365:.2f} €</td>"
                f"<td>{coste_tabla_red/12:.2f} €</td>"
                f"<td>{coste_tabla_red:.2f} €</td></tr>"
                f"<tr><td><b>🏦 Fees pool ({comision*100:.1f}%)</b></td>"
                f"<td>-{fees_tabla_red/365:.3f} €</td>"
                f"<td>-{fees_tabla_red/12:.3f} €</td>"
                f"<td>-{fees_tabla_red:.3f} €</td></tr>"
                f"<tr><td style='background:white;'><b>{'❌' if beneficio_tabla_red < 0 else '✅'} Beneficio neto</b></td>"
                f"<td style='background:{'white' if not red_activada else ('white' if beneficio_tabla_red == 0 else ('#ffcccc' if beneficio_tabla_red < 0 else '#e8f5e8'))};'><b>{beneficio_tabla_red/365:.2f} €</b></td>"
                f"<td style='background:{'white' if not red_activada else ('white' if beneficio_tabla_red == 0 else ('#ffcccc' if beneficio_tabla_red < 0 else '#e8f5e8'))};'><b>{beneficio_tabla_red/12:.2f} €</b></td>"
                f"<td style='background:{'white' if not red_activada else ('white' if beneficio_tabla_red == 0 else ('#ffcccc' if beneficio_tabla_red < 0 else '#e8f5e8'))};'><b>{beneficio_tabla_red:.2f} €</b></td></tr>"
                f"</table>"
                f"</div>"
                f"<br>"
                f"<br>"
                f"<div style='text-align:center;'>"
                f"<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse; text-align:center; margin:0 auto;'>"
                f"<tr><td>🪫 <b>Consumo anual</b></td><td>{consumo_red_anual:.1f} kWh</td></tr>"
                f"<tr><td>📈 <b>Rentabilidad bruta kWh</b></td><td style='background:{'white' if not red_activada else ('white' if euros_por_kwh_red_bruto == 0 else ('#ffcccc' if euros_por_kwh_red_bruto < 0 else '#e8f5e8'))};'>{euros_por_kwh_red_bruto:.3f} €/kWh</td></tr>"
                f"<tr><td>📉 <b>Rentabilidad neta kWh</b></td><td style='background:{'white' if not red_activada else ('white' if euros_por_kwh_red == 0 else ('#ffcccc' if euros_por_kwh_red < 0 else '#e8f5e8'))};'>{euros_por_kwh_red:.3f} €/kWh</td></tr>"
                f"</table>"
                f"</div>"
                f"<br>"
                f"<hr>"
                f"<br>"
                # SOLAR Y RED
                f"<div style='text-align:center;'><b>🌞 + 🏭 PRODUCCIÓN COMBINADA</b></div><br>"
                f"<div style='text-align:center;'>"
                f"<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse; text-align:center; margin:0 auto;'>"
                f"<tr style='background:#f5f5f5;'><th></th><th>DÍA</th><th>MES</th><th>AÑO</th></tr>"
                f"<tr><td><b>💶 Producción</b></td>"
                f"<td>{(produccion_tabla_solar + produccion_tabla_red)/365:.2f} €</td>"
                f"<td>{(produccion_tabla_solar + produccion_tabla_red)/12:.2f} €</td>"
                f"<td>{(produccion_tabla_solar + produccion_tabla_red):.2f} €</td></tr>"
                f"<tr><td><b>💡 + 💸 Gastos</b></td>"
                f"<td>{(coste_tabla_solar + coste_tabla_red)/365:.2f} €</td>"
                f"<td>{(coste_tabla_solar + coste_tabla_red)/12:.2f} €</td>"
                f"<td>{(coste_tabla_solar + coste_tabla_red):.2f} €</td></tr>"
                f"<tr><td><b>🏦 Fees pool ({comision*100:.1f}%)</b></td>"
                f"<td>-{(fees_tabla_solar + fees_tabla_red)/365:.3f} €</td>"
                f"<td>-{(fees_tabla_solar + fees_tabla_red)/12:.3f} €</td>"
                f"<td>-{(fees_tabla_solar + fees_tabla_red):.3f} €</td></tr>"
                f"<tr><td style='background:white;'><b>{'❌' if (beneficio_tabla_solar + beneficio_tabla_red) < 0 else '✅'} Beneficio neto</b></td>"
                f"<td style='background:{'white' if not solar_activado and not red_activada else ('white' if (beneficio_tabla_solar + beneficio_tabla_red) == 0 else ('#ffcccc' if (beneficio_tabla_solar + beneficio_tabla_red) < 0 else '#e8f5e8'))};'><b>{(beneficio_tabla_solar + beneficio_tabla_red)/365:.2f} €</b></td>"
                f"<td style='background:{'white' if not solar_activado and not red_activada else ('white' if (beneficio_tabla_solar + beneficio_tabla_red) == 0 else ('#ffcccc' if (beneficio_tabla_solar + beneficio_tabla_red) < 0 else '#e8f5e8'))};'><b>{(beneficio_tabla_solar + beneficio_tabla_red)/12:.2f} €</b></td>"
                f"<td style='background:{'white' if not solar_activado and not red_activada else ('white' if (beneficio_tabla_solar + beneficio_tabla_red) == 0 else ('#ffcccc' if (beneficio_tabla_solar + beneficio_tabla_red) < 0 else '#e8f5e8'))};'><b>{(beneficio_tabla_solar + beneficio_tabla_red):.2f} €</b></td></tr>"
                f"</table>"
                f"</div>"
                f"<br>"
                f"<br>"
                f"<div style='text-align:center;'>"
                f"<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse; text-align:center; margin:0 auto;'>"
                f"<tr><td>🪫 <b>Consumo anual total</b></td><td>{(energia_consumida_kwh + consumo_red_anual):.1f} kWh</td></tr>"
                f"<tr><td>📈 <b>Rentabilidad bruta kWh</b></td><td style='background:{'white' if not solar_activado and not red_activada else ('white' if rentabilidad_bruta_combinada == 0 else ('#ffcccc' if rentabilidad_bruta_combinada < 0 else '#e8f5e8'))};'>{rentabilidad_bruta_combinada:.3f} €/kWh</td></tr>"
                f"<tr><td>📉 <b>Rentabilidad neta kWh</b></td><td style='background:{'white' if not solar_activado and not red_activada else ('white' if rentabilidad_neta_combinada == 0 else ('#ffcccc' if rentabilidad_neta_combinada < 0 else '#e8f5e8'))};'>{rentabilidad_neta_combinada:.3f} €/kWh</td></tr>"
                f"</table>"
                f"</div>"
                f"<br>"
                f"<br>"
            )

            # Crear y mostrar ventana de resultados con efecto cascada
            nombre_minero = self.combo_minero.currentText()
            
            # Limpiar ventanas cerradas antes de calcular el offset
            self.limpiar_ventanas_cerradas()
            self.limpiar_figuras_cerradas()
            offset_cascada = len(self.ventanas_resultados)  # Cada nueva ventana tendrá un offset mayor
            
            ventana_resultados = VentanaResultados(resultado, nombre_minero, self, offset_cascada)
            self.ventanas_resultados.append(ventana_resultados)  # Mantener referencia
            ventana_resultados.show()
            
            # Beneficio neto anual combinado (solar + red)
            beneficio_anual = produccion_total
            inversion = precio_equipo
            self.mostrar_grafica_amortizacion(beneficio_anual, inversion, nombre_minero, ventana_resultados, offset_cascada)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Datos inválidos: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ventana = CalculadoraMineria()
    ventana.show()
    sys.exit(app.exec_())