Attribute VB_Name = "modNormas"
Option Explicit

' ============================================================
' Acceso a las normas parametrizadas (hojas Config_*).
' SDD secciones 11 y 12: las normas NO viven en el codigo sino
' en Config_Normas / Config_Escalas, con versionado y vigencia.
' Un cambio de norma = agregar filas de una NUEVA version;
' las versiones historicas nunca se sobrescriben (CA-009).
' ============================================================

' Columnas de Config_Normas
Public Const CN_PRODUCTO As Long = 1
Public Const CN_VERSION As Long = 2
Public Const CN_NORMA_REF As Long = 3
Public Const CN_VIG_DESDE As Long = 4
Public Const CN_VIG_HASTA As Long = 5
Public Const CN_ESTADO As Long = 6
Public Const CN_RUBRO As Long = 7
Public Const CN_NOMBRE As Long = 8
Public Const CN_UNIDAD As Long = 9
Public Const CN_OBLIGATORIO As Long = 10
Public Const CN_TIPO As Long = 11
Public Const CN_BASE As Long = 12
Public Const CN_TOLERANCIA As Long = 13
Public Const CN_FACTOR As Long = 14
Public Const CN_FACTOR_BONIF As Long = 15
Public Const CN_FACTOR_REBAJA As Long = 16
Public Const CN_MANIPULEO As Long = 17
Public Const CN_MAX_PCT As Long = 18
Public Const CN_MIN As Long = 19
Public Const CN_MAX As Long = 20
Public Const CN_FORMULA As Long = 21

' Columnas de Config_Escalas
Public Const CE_PRODUCTO As Long = 1
Public Const CE_VERSION As Long = 2
Public Const CE_RUBRO As Long = 3
Public Const CE_DESDE As Long = 4
Public Const CE_HASTA As Long = 5
Public Const CE_TIPO As Long = 6
Public Const CE_PCT As Long = 7

Private Function HojaNormas() As Worksheet
    Set HojaNormas = ThisWorkbook.Worksheets("Config_Normas")
End Function

' El producto existe y esta activo en Config_Productos.
Public Function ProductoExiste(ByVal producto As String) As Boolean
    Dim ws As Worksheet, fila As Long, cod As String
    Set ws = ThisWorkbook.Worksheets("Config_Productos")
    cod = Normalizar(producto)
    For fila = 2 To UltimaFila(ws, 1)
        If Normalizar(CStr(ws.Cells(fila, 1).Value)) = cod Then
            ProductoExiste = (Normalizar(CStr(ws.Cells(fila, 3).Value)) = "SI")
            Exit Function
        End If
    Next fila
End Function

Public Function NombreProducto(ByVal producto As String) As String
    Dim ws As Worksheet, fila As Long, cod As String
    Set ws = ThisWorkbook.Worksheets("Config_Productos")
    cod = Normalizar(producto)
    For fila = 2 To UltimaFila(ws, 1)
        If Normalizar(CStr(ws.Cells(fila, 1).Value)) = cod Then
            NombreProducto = CStr(ws.Cells(fila, 2).Value)
            Exit Function
        End If
    Next fila
    NombreProducto = producto
End Function

' Version de norma vigente para el producto en la fecha dada.
' Si hay varias vigentes gana la de VigenciaDesde mas reciente.
' Devuelve "" si no hay ninguna (imposibilidad de determinar la norma).
Public Function VersionVigente(ByVal producto As String, ByVal fecha As Date, _
                               ByRef normaRef As String) As String
    Dim ws As Worksheet, fila As Long, cod As String
    Dim mejorDesde As Date, desde As Date, hasta As Variant
    Dim encontrada As Boolean
    Set ws = HojaNormas()
    cod = Normalizar(producto)
    For fila = 2 To UltimaFila(ws, CN_PRODUCTO)
        If Normalizar(CStr(ws.Cells(fila, CN_PRODUCTO).Value)) = cod Then
            desde = CDate(ws.Cells(fila, CN_VIG_DESDE).Value)
            hasta = ws.Cells(fila, CN_VIG_HASTA).Value
            If desde <= fecha And (IsEmpty(hasta) Or CStr(hasta) = "" _
                                   Or CDate(hasta) >= fecha) Then
                If Not encontrada Or desde > mejorDesde Then
                    encontrada = True
                    mejorDesde = desde
                    VersionVigente = CStr(ws.Cells(fila, CN_VERSION).Value)
                    normaRef = CStr(ws.Cells(fila, CN_NORMA_REF).Value)
                End If
            End If
        End If
    Next fila
    If Not encontrada Then VersionVigente = ""
End Function

' Rubros configurados del producto para su norma vigente en la fecha.
' Lanza error si no hay norma vigente.
Public Function ObtenerRubros(ByVal producto As String, ByVal fecha As Date, _
                              ByRef normaRef As String, _
                              ByRef versionNorma As String) As Collection
    Dim ws As Worksheet, fila As Long, cod As String
    Dim rubros As New Collection, r As clsRubro
    Set ws = HojaNormas()
    cod = Normalizar(producto)

    versionNorma = VersionVigente(producto, fecha, normaRef)
    If versionNorma = "" Then
        Err.Raise vbObjectError + 100, "modNormas", _
            "No hay norma vigente para " & producto & " al " & Format(fecha, "dd/mm/yyyy")
    End If

    For fila = 2 To UltimaFila(ws, CN_PRODUCTO)
        If Normalizar(CStr(ws.Cells(fila, CN_PRODUCTO).Value)) = cod _
           And CStr(ws.Cells(fila, CN_VERSION).Value) = versionNorma Then
            Set r = New clsRubro
            r.Producto = cod
            r.VersionNorma = versionNorma
            r.NormaRef = normaRef
            r.Codigo = Normalizar(CStr(ws.Cells(fila, CN_RUBRO).Value))
            r.Nombre = CStr(ws.Cells(fila, CN_NOMBRE).Value)
            r.Unidad = CStr(ws.Cells(fila, CN_UNIDAD).Value)
            r.Obligatorio = (Normalizar(CStr(ws.Cells(fila, CN_OBLIGATORIO).Value)) = "SI")
            r.TipoCalculo = Normalizar(CStr(ws.Cells(fila, CN_TIPO).Value))
            r.Base = ws.Cells(fila, CN_BASE).Value
            r.Tolerancia = Val(ws.Cells(fila, CN_TOLERANCIA).Value & "")
            r.Factor = Val(ws.Cells(fila, CN_FACTOR).Value & "")
            r.FactorBonif = Val(ws.Cells(fila, CN_FACTOR_BONIF).Value & "")
            r.FactorRebaja = Val(ws.Cells(fila, CN_FACTOR_REBAJA).Value & "")
            r.Manipuleo = Val(ws.Cells(fila, CN_MANIPULEO).Value & "")
            r.MaxPct = ws.Cells(fila, CN_MAX_PCT).Value
            r.MinLogico = ws.Cells(fila, CN_MIN).Value
            r.MaxLogico = ws.Cells(fila, CN_MAX).Value
            r.Formula = CStr(ws.Cells(fila, CN_FORMULA).Value)
            rubros.Add r, r.Codigo
        End If
    Next fila
    Set ObtenerRubros = rubros
End Function

' Busca en Config_Escalas el rango [Desde, Hasta) que contiene el valor.
Public Function BuscarEscala(ByVal producto As String, ByVal versionNorma As String, _
                             ByVal rubro As String, ByVal valor As Double, _
                             ByRef tipo As String, ByRef pct As Double) As Boolean
    Dim ws As Worksheet, fila As Long
    Dim desde As Variant, hasta As Variant
    Set ws = ThisWorkbook.Worksheets("Config_Escalas")
    For fila = 2 To UltimaFila(ws, CE_PRODUCTO)
        If Normalizar(CStr(ws.Cells(fila, CE_PRODUCTO).Value)) = Normalizar(producto) _
           And CStr(ws.Cells(fila, CE_VERSION).Value) = versionNorma _
           And Normalizar(CStr(ws.Cells(fila, CE_RUBRO).Value)) = Normalizar(rubro) Then
            desde = ws.Cells(fila, CE_DESDE).Value
            hasta = ws.Cells(fila, CE_HASTA).Value
            If (IsEmpty(desde) Or CStr(desde) = "" Or valor >= CDbl(desde)) _
               And (IsEmpty(hasta) Or CStr(hasta) = "" Or valor < CDbl(hasta)) Then
                tipo = Normalizar(CStr(ws.Cells(fila, CE_TIPO).Value))
                pct = CDbl(ws.Cells(fila, CE_PCT).Value)
                BuscarEscala = True
                Exit Function
            End If
        End If
    Next fila
End Function
