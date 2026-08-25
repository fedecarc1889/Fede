VERSION 1.0 CLASS
BEGIN
  MultiUse = -1  'True
END
Attribute VB_Name = "clsRubro"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = False
Attribute VB_Exposed = False
Option Explicit

' Configuracion de un rubro de calidad segun la norma vigente
' (una fila de la hoja Config_Normas). SDD seccion 11.

Public Producto As String
Public VersionNorma As String
Public NormaRef As String
Public Codigo As String
Public Nombre As String
Public Unidad As String
Public Obligatorio As Boolean
Public TipoCalculo As String     ' REBAJA_POR_EXCESO / MERMA_POR_EXCESO /
                                 ' BONIFICACION_REBAJA_LINEAL / ESCALA / SIN_AJUSTE
Public Base As Variant           ' puede no aplicar (Empty)
Public Tolerancia As Double
Public Factor As Double
Public FactorBonif As Double
Public FactorRebaja As Double
Public Manipuleo As Double
Public MaxPct As Variant         ' tope opcional (Empty = sin tope)
Public MinLogico As Variant      ' rango logico de validacion
Public MaxLogico As Variant
Public Formula As String         ' descripcion de la regla (trazabilidad)
