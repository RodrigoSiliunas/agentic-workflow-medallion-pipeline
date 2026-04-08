from pipeline_lib.extractors.vehicle import extract


class TestVehicleExtract:
    def test_onix_2015(self):
        result = extract("Onix ano 2015 cor prata, placa SYL8V26")
        assert result["brand"] == "chevrolet"
        assert result["model"] == "onix"
        assert result["year"] == "2015"

    def test_civic_2016(self):
        result = extract("eh Civic 2016.. placa XPZ9O36")
        assert result["brand"] == "honda"
        assert result["model"] == "civic"
        assert result["year"] == "2016"

    def test_gol_2015(self):
        result = extract("Gol ano 2015 cor prata")
        assert result["brand"] == "volkswagen"
        assert result["model"] == "gol"

    def test_honda_civic_completo(self):
        result = extract("Honda Civic ano 2018")
        assert result["brand"] == "honda"
        assert result["model"] == "civic"
        assert result["year"] == "2018"

    def test_sem_veiculo(self):
        result = extract("oi, quero seguro")
        assert result["model"] is None

    def test_texto_vazio(self):
        result = extract("")
        assert result["model"] is None
