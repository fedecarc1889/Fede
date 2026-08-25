Attribute VB_Name = "modMotor"
Option Explicit

' ============================================================
' Quality Resolver + Rules Engine (SDD secciones 6, 11 y 19).
'
' Resolver (prioridad evaluada rubro por rubro):
'   RN-001  Planta y Camara -> se usa Camara
'   RN-002  solo Planta     -> Planta
'   RN-003  solo Camara     -> Camara
'   RN-004  ninguno         -> Empty (NULL). El 0 es valor valido.
'
' El motor ejecuta la regla parametrizada de Config_Normas:
' no contiene numeros fijos de ninguna norma.
'
' La carga manual y la importacion usan CalcularCTG, el MISMO
' motor con identico resultado ante identica entrada (CA-006/7).
' ============================================================

' valor_valido = valor_camara ?? valor_planta  (por rubro)
Public Sub ResolverValor(ByVal planta As Variant, ByVal camara As Variant, _
                         ByRef valor As Variant, ByRef origen As String)
    If Not IsEmpty(camara) Then
        valor = camara
        origen = "CAMARA"
    ElseIf Not IsEmpty(planta) Then
        valor = planta
        origen = "PLANTA"
    Else
        valor = Empty
        origen = ""
    End If
End Sub

Private Function Redondear(ByVal x As Double) As Double
    Redondear = WorksheetFunction.Round(x, 4)
End Function

Private Function AplicarTope(ByVal pct As Double, ByVal tope As Variant) As Double
    If IsEmpty(tope) Or CStr(tope) = "" Then
        AplicarTope = pct
    ElseIf pct > CDbl(tope) Then
        AplicarTope = CDbl(tope)
    Else
        AplicarTope = pct
    End If
End Function

' Aplica la regla configurada de un rubro sobre sus valores Planta/Camara.
Public Function AplicarRegla(ByVal cfg As clsRubro, _
                             ByVal planta As Variant, ByVal camara As Variant) As clsResultadoRubro
    Dim res As New clsResultadoRubro
    Dim valor As Variant, origen As String
    Dim v As Double, base As Double, pct As Double
    Dim tipoEsc As String, pctEsc As Double

    Set res.Cfg = cfg
    res.Planta = planta
    res.Camara = camara
    ResolverValor planta, camara, valor, origen
    res.ValorValido = valor
    res.Origen = origen
    res.TipoAjuste = "SIN_AJUSTE"
    res.Porcentaje = 0

    If IsEmpty(valor) Then
        res.TipoAjuste = "SIN_DATO"
        If cfg.Obligatorio Then
            res.Advertencia = "Rubro obligatorio '" & cfg.Nombre & _
                              "' sin analisis (ni Planta ni Camara)."
        End If
        Set AplicarRegla = res
        Exit Function
    End If

    v = CDbl(valor)

    ' Validacion de rango logico
    If Not IsEmpty(cfg.MinLogico) And CStr(cfg.MinLogico) <> "" Then
        If v < CDbl(cfg.MinLogico) Then _
            res.Advertencia = "Valor " & v & " fuera de rango logico para '" & cfg.Nombre & "'."
    End If
    If Not IsEmpty(cfg.MaxLogico) And CStr(cfg.MaxLogico) <> "" Then
        If v > CDbl(cfg.MaxLogico) Then _
            res.Advertencia = "Valor " & v & " fuera de rango logico para '" & cfg.Nombre & "'."
    End If

    Select Case cfg.TipoCalculo
        Case "SIN_AJUSTE"
            ' informativo, sin ajuste

        Case "REBAJA_POR_EXCESO"
            base = CDbl(cfg.Base)
            If v > base + cfg.Tolerancia Then
                pct = AplicarTope((v - base) * cfg.Factor, cfg.MaxPct)
                res.TipoAjuste = "REBAJA"
                res.Porcentaje = Redondear(pct)
            End If

        Case "MERMA_POR_EXCESO"
            base = CDbl(cfg.Base)
            If v > base + cfg.Tolerancia Then
                pct = AplicarTope((v - base) * cfg.Factor + cfg.Manipuleo, cfg.MaxPct)
                res.TipoAjuste = "MERMA"
                res.Porcentaje = Redondear(pct)
            End If

        Case "BONIFICACION_REBAJA_LINEAL"
            base = CDbl(cfg.Base)
            If v > base Then
                res.TipoAjuste = "BONIFICACION"
                res.Porcentaje = Redondear(AplicarTope((v - base) * cfg.FactorBonif, cfg.MaxPct))
            ElseIf v < base Then
                res.TipoAjuste = "REBAJA"
                res.Porcentaje = Redondear(AplicarTope((base - v) * cfg.FactorRebaja, cfg.MaxPct))
            End If

        Case "ESCALA"
            If BuscarEscala(cfg.Producto, cfg.VersionNorma, cfg.Codigo, v, tipoEsc, pctEsc) Then
                res.TipoAjuste = tipoEsc
                res.Porcentaje = Redondear(pctEsc)
            End If

        Case Else
            Err.Raise vbObjectError + 101, "modMotor", _
                "Tipo de calculo desconocido '" & cfg.TipoCalculo & "' en rubro " & cfg.Codigo
    End Select

    Set AplicarRegla = res
End Function

' ------------------------------------------------------------
' Nucleo compartido: calcula todos los rubros de un CTG.
'   mediciones: Collection de Array(codigoRubro, planta, camara)
' Devuelve Collection de clsResultadoRubro (uno por rubro de la
' norma) y completa normaRef/versionNorma/advertencias.
' ------------------------------------------------------------
Public Function CalcularCTG(ByVal producto As String, ByVal fecha As Date, _
                            ByVal mediciones As Collection, _
                            ByRef normaRef As String, ByRef versionNorma As String, _
                            ByRef advertencias As Collection) As Collection
    Dim rubros As Collection, resultados As New Collection
    Dim cfg As clsRubro, res As clsResultadoRubro
    Dim m As Variant, planta As Variant, camara As Variant
    Dim conocido As Boolean

    Set rubros = ObtenerRubros(producto, fecha, normaRef, versionNorma)

    ' Rubros desconocidos para el producto -> advertencia (se ignoran)
    For Each m In mediciones
        conocido = False
        For Each cfg In rubros
            If cfg.Codigo = CStr(m(0)) Then conocido = True
        Next cfg
        If Not conocido Then _
            advertencias.Add "Rubro desconocido para " & producto & ": " & m(0) & " (ignorado)."
    Next m

    For Each cfg In rubros
        planta = Empty
        camara = Empty
        For Each m In mediciones
            If CStr(m(0)) = cfg.Codigo Then
                planta = m(1)
                camara = m(2)
            End If
        Next m
        Set res = AplicarRegla(cfg, planta, camara)
        If res.Advertencia <> "" Then advertencias.Add res.Advertencia
        resultados.Add res
    Next cfg

    Set CalcularCTG = resultados
End Function

' Totales de un CTG. Las mermas se informan SEPARADAS de las
' bonificaciones/rebajas comerciales (SDD seccion 8).
Public Sub TotalesCTG(ByVal resultados As Collection, _
                      ByRef bonif As Double, ByRef rebaja As Double, _
                      ByRef merma As Double, ByRef neto As Double)
    Dim res As clsResultadoRubro
    bonif = 0: rebaja = 0: merma = 0
    For Each res In resultados
        Select Case res.TipoAjuste
            Case "BONIFICACION": bonif = bonif + res.Porcentaje
            Case "REBAJA": rebaja = rebaja + res.Porcentaje
            Case "MERMA": merma = merma + res.Porcentaje
        End Select
    Next res
    neto = bonif - rebaja
End Sub
