Attribute VB_Name = "modTrazabilidad"
Option Explicit

' ============================================================
' Trazabilidad (SDD seccion 15): cada calculo se registra en la
' hoja "Trazabilidad" con una fila por rubro, incluyendo valores
' Planta/Camara, valor utilizado y origen, norma y version
' aplicadas, regla, resultado y fecha/hora. Registro append-only:
' permite auditar por que se obtuvo cada resultado aun despues
' de un cambio de norma (CA-009).
' ============================================================

Public Sub Registrar(ByVal contrato As String, ByVal ctg As String, _
                     ByVal producto As String, ByVal peso As Variant, _
                     ByVal normaRef As String, ByVal versionNorma As String, _
                     ByVal resultados As Collection, _
                     ByVal bonif As Double, ByVal rebaja As Double, _
                     ByVal neto As Double, ByVal merma As Double)
    Dim ws As Worksheet, fila As Long
    Dim res As clsResultadoRubro
    Dim marca As String

    Set ws = ThisWorkbook.Worksheets("Trazabilidad")
    marca = Format(Now, "yyyy-mm-dd hh:nn:ss")
    fila = UltimaFila(ws, 1)
    If fila < 2 Then fila = 1

    For Each res In resultados
        fila = fila + 1
        ws.Cells(fila, 1).Value = marca
        ws.Cells(fila, 2).Value = contrato
        ws.Cells(fila, 3).Value = ctg
        ws.Cells(fila, 4).Value = producto
        ws.Cells(fila, 5).Value = MostrarValor(peso)
        ws.Cells(fila, 6).Value = res.Cfg.Nombre
        ws.Cells(fila, 7).Value = MostrarValor(res.Planta)
        ws.Cells(fila, 8).Value = MostrarValor(res.Camara)
        ws.Cells(fila, 9).Value = MostrarValor(res.ValorValido)
        ws.Cells(fila, 10).Value = res.Origen
        ws.Cells(fila, 11).Value = normaRef
        ws.Cells(fila, 12).Value = versionNorma
        ws.Cells(fila, 13).Value = res.Cfg.Formula
        ws.Cells(fila, 14).Value = res.TipoAjuste
        ws.Cells(fila, 15).Value = res.PorcentajeConSigno()
        ws.Cells(fila, 16).Value = bonif
        ws.Cells(fila, 17).Value = rebaja
        ws.Cells(fila, 18).Value = neto
        ws.Cells(fila, 19).Value = merma
    Next res
End Sub
