Attribute VB_Name = "modImportacion"
Option Explicit

' ============================================================
' Modulo 2 - Importacion masiva (SDD secciones 9, 10, 14, 16, 20).
'
' La hoja "Datos" contiene las filas a procesar (pegadas a mano o
' traidas con "Importar archivo..."). Encabezados esperados:
'   Contrato | CTG | Producto | Toneladas | <Rubro> Planta | <Rubro> Camara | ...
' Los encabezados de rubro se detectan de forma flexible (acentos y
' mayusculas indistintos, abreviaturas ME/MG/PH/etc.).
'
' Los errores de una fila NO impiden procesar el resto: las filas
' rechazadas van a la hoja "Errores" con su motivo (SDD seccion 16).
'
' Cada CTG se calcula de forma independiente (CA-004) con el mismo
' motor que la carga manual (CA-006/7) y luego se consolida por
' contrato ponderando por toneladas (SDD seccion 14): nunca promedio
' simple si los CTG tienen cantidades diferentes.
' ============================================================

Private Type TResCTG
    contrato As String
    ctg As String
    producto As String
    nombreProd As String
    peso As Variant          ' Empty si no se informo
    normaRef As String
    versionNorma As String
    bonif As Double
    rebaja As Double
    merma As Double
    neto As Double
    advertencias As String
End Type

Private Sub PrepararSalida(ByVal nombre As String, ByVal encabezados As Variant)
    Dim ws As Worksheet, i As Long
    Set ws = ThisWorkbook.Worksheets(nombre)
    ws.Cells.Clear
    For i = LBound(encabezados) To UBound(encabezados)
        ws.Cells(1, i + 1).Value = encabezados(i)
    Next i
    With ws.Range(ws.Cells(1, 1), ws.Cells(1, UBound(encabezados) + 1))
        .Font.Bold = True
        .Interior.Color = RGB(46, 125, 50)
        .Font.Color = RGB(255, 255, 255)
    End With
End Sub

Public Sub ProcesarDatos()
    Dim wsDatos As Worksheet, wsCTG As Worksheet, wsDet As Worksheet
    Dim wsErr As Worksheet, wsRes As Worksheet
    Dim colContrato As Long, colCTG As Long, colProd As Long, colPeso As Long
    Dim pesoEnKilos As Boolean
    Dim rubroCols() As Long, rubroCodigos() As String, rubroOrigenes() As String
    Dim nRubros As Long
    Dim ultCol As Long, ultFila As Long, fila As Long, c As Long
    Dim enc As String, prefijo As String
    Dim filaCTG As Long, filaDet As Long, filaErr As Long, filaRes As Long
    Dim vistos As New Collection
    Dim resArr() As TResCTG, nRes As Long

    Set wsDatos = ThisWorkbook.Worksheets("Datos")
    Set wsCTG = ThisWorkbook.Worksheets("Resultados CTG")
    Set wsDet = ThisWorkbook.Worksheets("Detalle Calidad")
    Set wsErr = ThisWorkbook.Worksheets("Errores")
    Set wsRes = ThisWorkbook.Worksheets("Resumen Contratos")

    ' ---- Paso 2: validacion estructural de columnas ----
    ultCol = wsDatos.Cells(1, wsDatos.Columns.Count).End(xlToLeft).Column
    ReDim rubroCols(1 To ultCol)
    ReDim rubroCodigos(1 To ultCol)
    ReDim rubroOrigenes(1 To ultCol)
    nRubros = 0

    For c = 1 To ultCol
        enc = Normalizar(CStr(wsDatos.Cells(1, c).Value))
        Select Case enc
            Case "CONTRATO", "NRO CONTRATO", "NUMERO CONTRATO"
                colContrato = c
            Case "CTG", "NRO CTG", "NUMERO CTG"
                colCTG = c
            Case "PRODUCTO", "GRANO", "CEREAL"
                colProd = c
            Case "TONELADAS", "TN", "TONS", "PESO"
                colPeso = c: pesoEnKilos = False
            Case "KILOS", "KG", "KILOGRAMOS"
                colPeso = c: pesoEnKilos = True
            Case ""
                ' columna vacia: ignorar
            Case Else
                If Right$(enc, 7) = " PLANTA" Then
                    prefijo = Left$(enc, Len(enc) - 7)
                    nRubros = nRubros + 1
                    rubroCols(nRubros) = c
                    rubroCodigos(nRubros) = CodigoRubro(prefijo)
                    rubroOrigenes(nRubros) = "PLANTA"
                ElseIf Right$(enc, 7) = " CAMARA" Then
                    prefijo = Left$(enc, Len(enc) - 7)
                    nRubros = nRubros + 1
                    rubroCols(nRubros) = c
                    rubroCodigos(nRubros) = CodigoRubro(prefijo)
                    rubroOrigenes(nRubros) = "CAMARA"
                End If
        End Select
    Next c

    If colCTG = 0 Or colProd = 0 Then
        MsgBox "Faltan columnas obligatorias en la hoja Datos (CTG y/o Producto).", vbCritical
        Exit Sub
    End If
    If nRubros = 0 Then
        MsgBox "No se detecto ninguna columna de rubro ('<Rubro> Planta' / '<Rubro> Camara').", vbCritical
        Exit Sub
    End If

    ' ---- Preparar hojas de salida (SDD seccion 20) ----
    PrepararSalida "Resultados CTG", Array("Contrato", "CTG", "Producto", "Toneladas", _
        "Norma", "Version", "Bonificacion %", "Rebaja %", "Neto %", "Merma %", _
        "Fecha calculo", "Advertencias")
    PrepararSalida "Detalle Calidad", Array("Contrato", "CTG", "Producto", "Rubro", _
        "Unidad", "Planta", "Camara", "Valor valido", "Origen", "Base", "Norma", _
        "Version", "Regla", "Tipo ajuste", "Ajuste %")
    PrepararSalida "Errores", Array("Fila", "Contrato", "CTG", "Motivo del rechazo")
    PrepararSalida "Resumen Contratos", Array("Contrato", "Cant. CTG", "Toneladas", _
        "Consolidacion", "Bonificacion %", "Rebaja %", "Neto %", "Merma %", "Advertencias")

    filaCTG = 1: filaDet = 1: filaErr = 1
    ultFila = UltimaFila(wsDatos, colCTG)
    If ultFila < UltimaFila(wsDatos, colProd) Then ultFila = UltimaFila(wsDatos, colProd)
    ReDim resArr(1 To ultFila + 1)
    nRes = 0

    Application.ScreenUpdating = False

    Dim contrato As String, ctg As String, producto As String
    Dim peso As Variant, ok As Boolean, i As Long
    Dim clave As String, motivo As String
    Dim mediciones As Collection, advertencias As Collection
    Dim resultados As Collection, res As clsResultadoRubro
    Dim normaRef As String, versionNorma As String
    Dim bonif As Double, rebaja As Double, merma As Double, neto As Double
    Dim planta As Variant, camara As Variant
    Dim adv As Variant, advTexto As String
    Dim j As Long, valor As Variant

    For fila = 2 To ultFila
        ' fila totalmente vacia -> ignorar
        If Application.WorksheetFunction.CountA(wsDatos.Rows(fila)) = 0 Then GoTo Siguiente

        contrato = Trim$(CStr(IIf(colContrato > 0, wsDatos.Cells(fila, colContrato).Value, "")))
        ctg = Trim$(CStr(wsDatos.Cells(fila, colCTG).Value))
        producto = Trim$(CStr(wsDatos.Cells(fila, colProd).Value))
        motivo = ""

        ' ---- Validaciones por fila (SDD seccion 16) ----
        If ctg = "" Then
            motivo = "CTG vacio."
        ElseIf producto = "" Then
            motivo = "Producto vacio."
        ElseIf Not ProductoExiste(producto) Then
            motivo = "Producto inexistente o sin norma configurada: '" & producto & "'."
        End If

        If motivo = "" Then
            clave = contrato & "|" & ctg
            On Error Resume Next
            vistos.Add True, clave
            If Err.Number <> 0 Then motivo = "CTG duplicado en los datos (contrato '" & contrato & "')."
            On Error GoTo 0
        End If

        peso = Empty
        If motivo = "" And colPeso > 0 Then
            peso = ParseNumero(wsDatos.Cells(fila, colPeso).Value, ok)
            If Not ok Then motivo = "Valor de peso no numerico: '" & wsDatos.Cells(fila, colPeso).Value & "'."
            If ok And pesoEnKilos And Not IsEmpty(peso) Then peso = CDbl(peso) / 1000#
        End If

        ' ---- Paso 3: normalizacion al modelo interno ----
        If motivo = "" Then
            Set mediciones = New Collection
            For i = 1 To nRubros
                valor = ParseNumero(wsDatos.Cells(fila, rubroCols(i)).Value, ok)
                If Not ok Then
                    motivo = "Valor no numerico '" & wsDatos.Cells(fila, rubroCols(i)).Value & _
                             "' en columna '" & wsDatos.Cells(1, rubroCols(i)).Value & "'."
                    Exit For
                End If
                If Not IsEmpty(valor) Then
                    ' juntar Planta y Camara del mismo rubro
                    planta = Empty: camara = Empty
                    Dim encontrado As Boolean, m As Variant, k As Long
                    encontrado = False
                    For k = 1 To mediciones.Count
                        m = mediciones(k)
                        If CStr(m(0)) = rubroCodigos(i) Then
                            planta = m(1): camara = m(2)
                            mediciones.Remove k
                            encontrado = True
                            Exit For
                        End If
                    Next k
                    If rubroOrigenes(i) = "PLANTA" Then planta = valor Else camara = valor
                    mediciones.Add Array(rubroCodigos(i), planta, camara)
                End If
            Next i
        End If

        If motivo <> "" Then
            filaErr = filaErr + 1
            wsErr.Cells(filaErr, 1).Value = fila
            wsErr.Cells(filaErr, 2).Value = contrato
            wsErr.Cells(filaErr, 3).Value = ctg
            wsErr.Cells(filaErr, 4).Value = motivo
            GoTo Siguiente
        End If

        ' ---- Pasos 4-6: valor valido + norma + calculo (mismo motor) ----
        Set advertencias = New Collection
        On Error GoTo ErrCalculo
        Set resultados = CalcularCTG(producto, Date, mediciones, normaRef, versionNorma, advertencias)
        On Error GoTo 0
        GoTo CalculoOk

ErrCalculo:
        motivo = Err.Description
        Resume FilaConError
FilaConError:
        On Error GoTo 0
        filaErr = filaErr + 1
        wsErr.Cells(filaErr, 1).Value = fila
        wsErr.Cells(filaErr, 2).Value = contrato
        wsErr.Cells(filaErr, 3).Value = ctg
        wsErr.Cells(filaErr, 4).Value = motivo
        GoTo Siguiente

CalculoOk:
        TotalesCTG resultados, bonif, rebaja, merma, neto

        advTexto = ""
        For Each adv In advertencias
            advTexto = advTexto & IIf(advTexto = "", "", "; ") & CStr(adv)
        Next adv

        ' Resultado por CTG (SDD seccion 13)
        filaCTG = filaCTG + 1
        wsCTG.Cells(filaCTG, 1).Value = contrato
        wsCTG.Cells(filaCTG, 2).Value = ctg
        wsCTG.Cells(filaCTG, 3).Value = NombreProducto(producto)
        wsCTG.Cells(filaCTG, 4).Value = MostrarValor(peso)
        wsCTG.Cells(filaCTG, 5).Value = normaRef
        wsCTG.Cells(filaCTG, 6).Value = versionNorma
        wsCTG.Cells(filaCTG, 7).Value = bonif
        wsCTG.Cells(filaCTG, 8).Value = rebaja
        wsCTG.Cells(filaCTG, 9).Value = neto
        wsCTG.Cells(filaCTG, 10).Value = merma
        wsCTG.Cells(filaCTG, 11).Value = Format(Now, "yyyy-mm-dd hh:nn:ss")
        wsCTG.Cells(filaCTG, 12).Value = advTexto

        ' Detalle por rubro (SDD seccion 20, hoja "Detalle Calidad")
        For Each res In resultados
            filaDet = filaDet + 1
            wsDet.Cells(filaDet, 1).Value = contrato
            wsDet.Cells(filaDet, 2).Value = ctg
            wsDet.Cells(filaDet, 3).Value = NombreProducto(producto)
            wsDet.Cells(filaDet, 4).Value = res.Cfg.Nombre
            wsDet.Cells(filaDet, 5).Value = res.Cfg.Unidad
            wsDet.Cells(filaDet, 6).Value = MostrarValor(res.Planta)
            wsDet.Cells(filaDet, 7).Value = MostrarValor(res.Camara)
            wsDet.Cells(filaDet, 8).Value = MostrarValor(res.ValorValido)
            wsDet.Cells(filaDet, 9).Value = res.Origen
            wsDet.Cells(filaDet, 10).Value = MostrarValor(res.Cfg.Base)
            wsDet.Cells(filaDet, 11).Value = normaRef
            wsDet.Cells(filaDet, 12).Value = versionNorma
            wsDet.Cells(filaDet, 13).Value = res.Cfg.Formula
            wsDet.Cells(filaDet, 14).Value = res.TipoAjuste
            wsDet.Cells(filaDet, 15).Value = res.PorcentajeConSigno()
        Next res

        ' Trazabilidad
        Registrar contrato, ctg, producto, peso, normaRef, versionNorma, _
                  resultados, bonif, rebaja, neto, merma

        ' Guardar para consolidar por contrato
        nRes = nRes + 1
        resArr(nRes).contrato = contrato
        resArr(nRes).ctg = ctg
        resArr(nRes).producto = producto
        resArr(nRes).peso = peso
        resArr(nRes).bonif = bonif
        resArr(nRes).rebaja = rebaja
        resArr(nRes).merma = merma
        resArr(nRes).neto = neto

Siguiente:
    Next fila

    ' ---- Paso 7: consolidacion por contrato (SDD seccion 14) ----
    ConsolidarContratos resArr, nRes, wsRes

    Application.ScreenUpdating = True
    MsgBox "Proceso terminado." & vbCrLf & _
           "CTG procesados: " & nRes & vbCrLf & _
           "Filas rechazadas: " & (filaErr - 1), vbInformation
End Sub

' Consolida ponderando por toneladas. Si algun CTG del contrato no
' informa peso, usa promedio simple y lo advierte: nunca se promedian
' silenciosamente porcentajes con cantidades diferentes.
Private Sub ConsolidarContratos(ByRef resArr() As TResCTG, ByVal nRes As Long, _
                                ByVal wsRes As Worksheet)
    Dim contratos As New Collection, i As Long, j As Long
    Dim filaRes As Long

    For i = 1 To nRes
        On Error Resume Next
        contratos.Add resArr(i).contrato, "K" & resArr(i).contrato
        On Error GoTo 0
    Next i

    filaRes = 1
    Dim contrato As Variant
    For Each contrato In contratos
        Dim cant As Long, pesoTotal As Double, ponderado As Boolean
        Dim sB As Double, sR As Double, sM As Double
        Dim aB As Double, aR As Double, aM As Double
        cant = 0: pesoTotal = 0: ponderado = True
        sB = 0: sR = 0: sM = 0: aB = 0: aR = 0: aM = 0

        For j = 1 To nRes
            If resArr(j).contrato = CStr(contrato) Then
                cant = cant + 1
                If IsEmpty(resArr(j).peso) Then
                    ponderado = False
                ElseIf CDbl(resArr(j).peso) <= 0 Then
                    ponderado = False
                Else
                    pesoTotal = pesoTotal + CDbl(resArr(j).peso)
                End If
                aB = aB + resArr(j).bonif
                aR = aR + resArr(j).rebaja
                aM = aM + resArr(j).merma
            End If
        Next j

        If ponderado And pesoTotal > 0 Then
            For j = 1 To nRes
                If resArr(j).contrato = CStr(contrato) Then
                    sB = sB + resArr(j).bonif * CDbl(resArr(j).peso)
                    sR = sR + resArr(j).rebaja * CDbl(resArr(j).peso)
                    sM = sM + resArr(j).merma * CDbl(resArr(j).peso)
                End If
            Next j
            sB = sB / pesoTotal: sR = sR / pesoTotal: sM = sM / pesoTotal
        Else
            ponderado = False
            sB = aB / cant: sR = aR / cant: sM = aM / cant
        End If

        filaRes = filaRes + 1
        wsRes.Cells(filaRes, 1).Value = CStr(contrato)
        wsRes.Cells(filaRes, 2).Value = cant
        wsRes.Cells(filaRes, 3).Value = IIf(pesoTotal > 0, pesoTotal, "")
        wsRes.Cells(filaRes, 4).Value = IIf(ponderado, "Ponderada por toneladas", "Promedio simple")
        wsRes.Cells(filaRes, 5).Value = WorksheetFunction.Round(sB, 4)
        wsRes.Cells(filaRes, 6).Value = WorksheetFunction.Round(sR, 4)
        wsRes.Cells(filaRes, 7).Value = WorksheetFunction.Round(sB - sR, 4)
        wsRes.Cells(filaRes, 8).Value = WorksheetFunction.Round(sM, 4)
        If Not ponderado And cant > 1 Then
            wsRes.Cells(filaRes, 9).Value = "No todos los CTG informan toneladas: promedio simple."
        End If
    Next contrato
End Sub

' Trae la primera hoja de un archivo .xlsx externo a la hoja Datos.
Public Sub ImportarArchivo()
    Dim ruta As Variant, wb As Workbook, wsDatos As Worksheet
    ruta = Application.GetOpenFilename("Archivos Excel (*.xlsx;*.xls;*.xlsm), *.xlsx;*.xls;*.xlsm", , _
                                       "Seleccionar archivo a importar")
    If VarType(ruta) = vbBoolean Then Exit Sub

    Set wsDatos = ThisWorkbook.Worksheets("Datos")
    Application.ScreenUpdating = False
    Set wb = Workbooks.Open(CStr(ruta), ReadOnly:=True)
    wsDatos.Cells.Clear
    wb.Worksheets(1).UsedRange.Copy
    wsDatos.Range("A1").PasteSpecial xlPasteValues
    Application.CutCopyMode = False
    wb.Close SaveChanges:=False
    Application.ScreenUpdating = True
    MsgBox "Datos importados. Presione 'Procesar datos' para calcular.", vbInformation
End Sub

' Exporta las cuatro hojas de resultados a un libro nuevo (SDD seccion 20).
Public Sub ExportarResultados()
    Dim nombre As String
    nombre = ThisWorkbook.Path & Application.PathSeparator & _
             "Resultados_" & Format(Now, "yyyymmdd_hhnnss") & ".xlsx"
    Application.ScreenUpdating = False
    ThisWorkbook.Worksheets(Array("Resumen Contratos", "Resultados CTG", _
                                  "Detalle Calidad", "Errores")).Copy
    Application.DisplayAlerts = False
    ActiveWorkbook.SaveAs Filename:=nombre, FileFormat:=xlOpenXMLWorkbook
    Application.DisplayAlerts = True
    Application.ScreenUpdating = True
    MsgBox "Resultados exportados a:" & vbCrLf & nombre, vbInformation
End Sub
