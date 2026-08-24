Attribute VB_Name = "modCargaManual"
Option Explicit

' ============================================================
' Modulo 1 - Carga manual (SDD secciones 7 y 8).
' El usuario elige el producto, presiona "Cargar rubros" para
' traer los rubros de la norma vigente, ingresa valores Planta
' y/o Camara y presiona "Calcular". Usa el MISMO motor que la
' importacion Excel (CalcularCTG), garantizando CA-006/CA-007.
' ============================================================

Private Const FILA_ENC As Long = 9    ' fila de encabezados de la tabla
Private Const FILA_INI As Long = 10   ' primera fila de rubros
Private Const COL_RUBRO As Long = 2   ' B
Private Const COL_UNIDAD As Long = 3
Private Const COL_BASE As Long = 4
Private Const COL_PLANTA As Long = 5
Private Const COL_CAMARA As Long = 6
Private Const COL_VALIDO As Long = 7
Private Const COL_ORIGEN As Long = 8
Private Const COL_TIPO As Long = 9
Private Const COL_AJUSTE As Long = 10 ' J

Private Function Hoja() As Worksheet
    Set Hoja = ThisWorkbook.Worksheets("CargaManual")
End Function

Private Function FechaAnalisis(ByVal ws As Worksheet) As Date
    If IsDate(ws.Range("C6").Value) Then
        FechaAnalisis = CDate(ws.Range("C6").Value)
    Else
        FechaAnalisis = Date
    End If
End Function

' Trae los rubros configurados del producto seleccionado (SDD seccion 7).
Public Sub CargarRubros()
    Dim ws As Worksheet, producto As String
    Dim rubros As Collection, cfg As clsRubro
    Dim normaRef As String, versionNorma As String
    Dim fila As Long

    Set ws = Hoja()
    producto = Normalizar(CStr(ws.Range("C2").Value))
    If producto = "" Then
        MsgBox "Seleccione un producto en la celda C2.", vbExclamation
        Exit Sub
    End If
    If Not ProductoExiste(producto) Then
        MsgBox "Producto inexistente o inactivo: " & producto, vbExclamation
        Exit Sub
    End If

    On Error GoTo ErrNorma
    Set rubros = ObtenerRubros(producto, FechaAnalisis(ws), normaRef, versionNorma)
    On Error GoTo 0

    ws.Range(ws.Cells(FILA_INI, COL_RUBRO), ws.Cells(200, COL_AJUSTE + 2)).Clear
    fila = FILA_INI
    For Each cfg In rubros
        ws.Cells(fila, COL_RUBRO).Value = cfg.Nombre & IIf(cfg.Obligatorio, " *", "")
        ws.Cells(fila, COL_UNIDAD).Value = cfg.Unidad
        ws.Cells(fila, COL_BASE).Value = MostrarValor(cfg.Base)
        ws.Range(ws.Cells(fila, COL_PLANTA), ws.Cells(fila, COL_CAMARA)) _
          .Interior.Color = RGB(255, 255, 204)   ' celdas de carga
        fila = fila + 1
    Next cfg
    ws.Range("B8").Value = "Norma: " & normaRef & " (version " & versionNorma & ")"
    Exit Sub

ErrNorma:
    MsgBox Err.Description, vbExclamation
End Sub

' Calcula el CTG cargado manualmente y muestra el detalle (SDD seccion 8).
Public Sub CalcularManual()
    Dim ws As Worksheet, producto As String, fecha As Date
    Dim rubros As Collection, cfg As clsRubro
    Dim normaRef As String, versionNorma As String
    Dim mediciones As New Collection, advertencias As New Collection
    Dim resultados As Collection, res As clsResultadoRubro
    Dim fila As Long, i As Long, ok As Boolean
    Dim planta As Variant, camara As Variant, peso As Variant
    Dim bonif As Double, rebaja As Double, merma As Double, neto As Double
    Dim adv As Variant, texto As String

    Set ws = Hoja()
    producto = Normalizar(CStr(ws.Range("C2").Value))
    If Not ProductoExiste(producto) Then
        MsgBox "Producto inexistente o inactivo: " & producto, vbExclamation
        Exit Sub
    End If
    fecha = FechaAnalisis(ws)

    On Error GoTo ErrNorma
    Set rubros = ObtenerRubros(producto, fecha, normaRef, versionNorma)
    On Error GoTo 0

    ' Leer los valores fila por fila, en el orden de los rubros cargados
    fila = FILA_INI
    For Each cfg In rubros
        If InStr(CStr(ws.Cells(fila, COL_RUBRO).Value), cfg.Nombre) = 0 Then
            MsgBox "La tabla no coincide con el producto seleccionado." & vbCrLf & _
                   "Presione 'Cargar rubros' y vuelva a ingresar los valores.", vbExclamation
            Exit Sub
        End If
        planta = ParseNumero(ws.Cells(fila, COL_PLANTA).Value, ok)
        If Not ok Then
            MsgBox "Valor no numerico en " & cfg.Nombre & " (Planta).", vbExclamation
            Exit Sub
        End If
        camara = ParseNumero(ws.Cells(fila, COL_CAMARA).Value, ok)
        If Not ok Then
            MsgBox "Valor no numerico en " & cfg.Nombre & " (Camara).", vbExclamation
            Exit Sub
        End If
        mediciones.Add Array(cfg.Codigo, planta, camara)
        fila = fila + 1
    Next cfg

    peso = ParseNumero(ws.Range("C5").Value, ok)
    If Not ok Then
        MsgBox "Toneladas: valor no numerico.", vbExclamation
        Exit Sub
    End If

    ' Mismo motor que la importacion (CA-006 / CA-007)
    Set resultados = CalcularCTG(producto, fecha, mediciones, normaRef, versionNorma, advertencias)
    TotalesCTG resultados, bonif, rebaja, merma, neto

    ' Volcar resultados por rubro
    fila = FILA_INI
    For Each res In resultados
        ws.Cells(fila, COL_VALIDO).Value = MostrarValor(res.ValorValido)
        ws.Cells(fila, COL_ORIGEN).Value = IIf(res.Origen = "", "Sin analisis", res.Origen)
        ws.Cells(fila, COL_TIPO).Value = res.TipoAjuste
        If res.TipoAjuste = "SIN_DATO" Then
            ws.Cells(fila, COL_AJUSTE).Value = ""
        Else
            ws.Cells(fila, COL_AJUSTE).Value = res.PorcentajeConSigno() / 100
            ws.Cells(fila, COL_AJUSTE).NumberFormat = "+0.00%;-0.00%;0.00%"
        End If
        fila = fila + 1
    Next res

    ' Totales (mermas separadas de bonificaciones/rebajas comerciales)
    fila = fila + 1
    ws.Cells(fila, COL_TIPO).Value = "Bonificaciones"
    ws.Cells(fila, COL_AJUSTE).Value = bonif / 100
    ws.Cells(fila + 1, COL_TIPO).Value = "Rebajas"
    ws.Cells(fila + 1, COL_AJUSTE).Value = -rebaja / 100
    ws.Cells(fila + 2, COL_TIPO).Value = "Resultado neto"
    ws.Cells(fila + 2, COL_AJUSTE).Value = neto / 100
    ws.Cells(fila + 3, COL_TIPO).Value = "Merma (separada)"
    ws.Cells(fila + 3, COL_AJUSTE).Value = -merma / 100
    ws.Range(ws.Cells(fila, COL_TIPO), ws.Cells(fila + 3, COL_TIPO)).Font.Bold = True
    With ws.Range(ws.Cells(fila, COL_AJUSTE), ws.Cells(fila + 3, COL_AJUSTE))
        .NumberFormat = "+0.00%;-0.00%;0.00%"
        .Font.Bold = True
    End With

    ' Advertencias
    texto = ""
    For Each adv In advertencias
        texto = texto & IIf(texto = "", "", vbCrLf) & CStr(adv)
    Next adv
    ws.Cells(fila + 5, COL_RUBRO).Value = texto

    ' Trazabilidad
    Registrar CStr(ws.Range("C3").Value), CStr(ws.Range("C4").Value), _
              producto, peso, normaRef, versionNorma, resultados, _
              bonif, rebaja, neto, merma
    Exit Sub

ErrNorma:
    MsgBox Err.Description, vbExclamation
End Sub
