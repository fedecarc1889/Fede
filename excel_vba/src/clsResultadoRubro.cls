VERSION 1.0 CLASS
BEGIN
  MultiUse = -1  'True
END
Attribute VB_Name = "clsResultadoRubro"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = False
Attribute VB_Exposed = False
Option Explicit

' Resultado del calculo de un rubro, con trazabilidad completa
' (SDD secciones 13 y 15).

Public Cfg As clsRubro
Public Planta As Variant         ' Empty = sin analisis de Planta
Public Camara As Variant         ' Empty = sin analisis de Camara
Public ValorValido As Variant    ' Empty = RN-004 (sin analisis)
Public Origen As String          ' "CAMARA" / "PLANTA" / ""
Public TipoAjuste As String      ' BONIFICACION / REBAJA / MERMA / SIN_AJUSTE / SIN_DATO
Public Porcentaje As Double      ' magnitud, siempre >= 0
Public Advertencia As String

' Bonificacion positiva; rebaja y merma negativas.
Public Function PorcentajeConSigno() As Double
    Select Case TipoAjuste
        Case "BONIFICACION": PorcentajeConSigno = Porcentaje
        Case "REBAJA", "MERMA": PorcentajeConSigno = -Porcentaje
        Case Else: PorcentajeConSigno = 0
    End Select
End Function
