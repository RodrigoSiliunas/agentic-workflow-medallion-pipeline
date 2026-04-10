from pipeline_lib.masking.format_preserving import mask_cpf, mask_email, mask_phone, mask_plate


class TestMaskCpf:
    def test_preserva_formato(self):
        assert mask_cpf("383.182.856-05") == "***.***.856-05"

    def test_preserva_ultimos_5(self):
        result = mask_cpf("942.968.827-69")
        assert result.endswith("827-69")

    def test_cpf_invalido(self):
        assert mask_cpf("abc") == "***.***.***-**"


class TestMaskEmail:
    def test_preserva_dominio(self):
        assert mask_email("joao.silva@gmail.com") == "j********a@gmail.com"

    def test_email_curto(self):
        result = mask_email("ab@gmail.com")
        assert result.endswith("@gmail.com")

    def test_dominio_intacto(self):
        result = mask_email("lucas.souza@outlook.com")
        assert "@outlook.com" in result


class TestMaskPhone:
    def test_preserva_ddd_e_final(self):
        result = mask_phone("(11) 98765-4321")
        assert result == "(11) ****-4321"

    def test_telefone_so_digitos(self):
        result = mask_phone("11987654321")
        assert result.startswith("(11)")
        assert result.endswith("4321")


class TestMaskPlate:
    def test_mascara_placa(self):
        result = mask_plate("SYL8V26")
        assert result == "S**8*26"
        assert len(result) == 7

    def test_placa_invalida(self):
        assert mask_plate("AB") == "***-****"
