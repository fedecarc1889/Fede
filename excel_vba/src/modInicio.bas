Attribute VB_Name = "modInicio"
Option Explicit

' ============================================================
' Inicializacion del libro: crea los botones y la lista
' desplegable de productos. Ejecutar UNA VEZ despues de importar
' los modulos (Alt+F8 -> Inicializar). Es idempotente: puede
' volver a ejecutarse sin duplicar botones.
' ============================================================

Private Sub CrearBoton(ByVal ws As Worksheet, ByVal celda As String, _
                       ByVal texto As String, ByVal macro As String)
    Dim btn As Button
    With ws.Range(celda)
        Set btn = ws.Buttons.Add(.Left, .Top, 110, 28)
    End With
    btn.Caption = texto
    btn.OnAction = macro
End Sub

Public Sub Inicializar()
    Dim wsCM As Worksheet, wsDatos As Worksheet

    Set wsCM = ThisWorkbook.Worksheets("CargaManual")
    Set wsDatos = ThisWorkbook.Worksheets("Datos")

    wsCM.Buttons.Delete
    wsDatos.Buttons.Delete

    CrearBoton wsCM, "E2", "Cargar rubros", "CargarRubros"
    CrearBoton wsCM, "E4", "Calcular", "CalcularManual"

    CrearBoton wsDatos, "N1", "Procesar datos", "ProcesarDatos"
    CrearBoton wsDatos, "N4", "Importar archivo...", "ImportarArchivo"
    CrearBoton wsDatos, "N7", "Exportar resultados", "ExportarResultados"

    ' Lista desplegable de productos en CargaManual!C2
    With wsCM.Range("C2").Validation
        .Delete
        .Add Type:=xlValidateList, AlertStyle:=xlValidAlertStop, _
             Formula1:="=Config_Productos!$A$2:$A$100"
        .IgnoreBlank = True
        .InCellDropdown = True
    End With

    MsgBox "Listo. La calculadora quedo configurada." & vbCrLf & vbCrLf & _
           "CargaManual: elija un producto, 'Cargar rubros', ingrese valores y 'Calcular'." & vbCrLf & _
           "Datos: pegue o importe filas y presione 'Procesar datos'.", vbInformation
End Sub
