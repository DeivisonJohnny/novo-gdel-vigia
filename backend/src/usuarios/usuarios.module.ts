import { Module } from "@nestjs/common";
import { ComumModule } from "../comum/comum.module";
import { SegurancaModule } from "../seguranca/seguranca.module";
import { UsuariosController } from "./usuarios.controller";
import { UsuariosService } from "./usuarios.service";

@Module({
  imports: [SegurancaModule, ComumModule],
  controllers: [UsuariosController],
  providers: [UsuariosService],
})
export class UsuariosModule {}
