import { Module } from "@nestjs/common";
import { ComumModule } from "../comum/comum.module";
import { SegurancaModule } from "../seguranca/seguranca.module";
import { AutenticacaoController } from "./autenticacao.controller";
import { AutenticacaoService } from "./autenticacao.service";

@Module({
  imports: [SegurancaModule, ComumModule],
  controllers: [AutenticacaoController],
  providers: [AutenticacaoService],
})
export class AutenticacaoModule {}
