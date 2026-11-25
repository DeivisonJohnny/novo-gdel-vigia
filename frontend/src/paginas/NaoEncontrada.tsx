import { Link } from "react-router-dom";
import { EstadoVazio } from "@/componentes/ui/Estados";

export function NaoEncontrada() {
  return (
    <div className="py-16">
      <EstadoVazio titulo="Página não encontrada" descricao="O endereço não existe ou você não tem acesso a ele." />
      <p className="text-center">
        <Link to="/" className="text-sm font-medium text-primaria">
          Voltar para a visão geral
        </Link>
      </p>
    </div>
  );
}
