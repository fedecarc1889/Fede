Attribute VB_Name = "modUtiles"
Option Explicit

' ============================================================
' Utilidades generales: normalizacion de textos y parseo.
' Regla critica (SDD RN-004 / seccion 19): una celda vacia es
' "sin analisis" (Empty). NUNCA se interpreta como cero.
' El valor 0 SI es un analisis valido.
' ============================================================

' Quita acentos, pasa a mayusculas y colapsa espacios.
Public Function Normalizar(ByVal s As String) As String
    Const ACENTOS As String = "áàäâÁÀÄÂéèëêÉÈËÊíìïîÍÌÏÎóòöôÓÒÖÔúùüûÚÙÜÛñÑ"
    Const PLANOS As String = "aaaaAAAAeeeeEEEEiiiiIIIIooooOOOOuuuuUUUUnN"
    Dim t As String, i As Long
    t = Trim$(s)
    For i = 1 To Len(ACENTOS)
        t = Replace(t, Mid$(ACENTOS, i, 1), Mid$(PLANOS, i, 1))
    Next i
    t = UCase$(t)
    Do While InStr(t, "  ") > 0
        t = Replace(t, "  ", " ")
    Loop
    Normalizar = t
End Function

' Convierte un nombre de rubro a codigo interno: "Materias extrañas"
' -> "MATERIAS_EXTRANAS". Acepta tambien abreviaturas comerciales.
Public Function CodigoRubro(ByVal s As String) As String
    Dim t As String
    t = Normalizar(s)
    t = Replace(t, "/", " ")
    t = Replace(t, "  ", " ")
    t = Replace(t, " ", "_")
    CodigoRubro = AliasRubro(t)
End Function

' Abreviaturas habituales en planillas -> codigo interno.
Public Function AliasRubro(ByVal codigo As String) As String
    Select Case codigo
        Case "ME", "MMEE": AliasRubro = "MATERIAS_EXTRANAS"
        Case "CE": AliasRubro = "CUERPOS_EXTRANOS"
        Case "HUM": AliasRubro = "HUMEDAD"
        Case "MG": AliasRubro = "MATERIA_GRASA"
        Case "PH": AliasRubro = "PESO_HECTOLITRICO"
        Case "DANADOS": AliasRubro = "GRANOS_DANADOS"
        Case "VERDES": AliasRubro = "GRANOS_VERDES"
        Case "QUEBRADOS": AliasRubro = "GRANOS_QUEBRADOS"
        Case Else: AliasRubro = codigo
    End Select
End Function

' Valida que un texto sea un numero con punto decimal (tras normalizar).
Private Function EsNumeroPunto(ByVal s As String) As Boolean
    Dim i As Long, c As String, puntos As Long, digitos As Long
    If Len(s) = 0 Then Exit Function
    For i = 1 To Len(s)
        c = Mid$(s, i, 1)
        Select Case c
            Case "0" To "9": digitos = digitos + 1
            Case ".": puntos = puntos + 1
            Case "-", "+": If i > 1 Then Exit Function
            Case Else: Exit Function
        End Select
    Next i
    EsNumeroPunto = (digitos > 0 And puntos <= 1)
End Function

' Convierte una celda a numero.
'   - Vacio -> Empty (sin analisis), ok = True
'   - Numero -> Double, ok = True
'   - Texto numerico ("14,2" / "14.2" / "1.234,56") -> Double, ok = True
'   - Otro texto -> Empty, ok = False
Public Function ParseNumero(ByVal v As Variant, ByRef ok As Boolean) As Variant
    Dim s As String
    ok = True
    ParseNumero = Empty
    If IsEmpty(v) Or IsNull(v) Then Exit Function
    If IsNumeric(v) And VarType(v) <> vbString Then
        ParseNumero = CDbl(v)
        Exit Function
    End If
    s = Trim$(CStr(v))
    If s = "" Then Exit Function
    s = Replace(s, " ", "")
    s = Replace(s, "%", "")
    If InStr(s, ",") > 0 And InStr(s, ".") > 0 Then
        s = Replace(s, ".", "")   ' "1.234,56": el punto es miles
    End If
    s = Replace(s, ",", ".")
    If Not EsNumeroPunto(s) Then
        ok = False
        Exit Function
    End If
    ParseNumero = Val(s)
End Function

' Formatea un Variant que puede ser Empty para mostrar en celdas.
Public Function MostrarValor(ByVal v As Variant) As Variant
    If IsEmpty(v) Then
        MostrarValor = ""
    Else
        MostrarValor = v
    End If
End Function

' Ultima fila con datos de una hoja segun la columna indicada.
Public Function UltimaFila(ByVal ws As Worksheet, ByVal col As Long) As Long
    UltimaFila = ws.Cells(ws.Rows.Count, col).End(xlUp).Row
End Function
