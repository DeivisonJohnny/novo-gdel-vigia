import { Module } from "@nestjs/common";
import { AutenticacaoModule } from "./autenticacao/autenticacao.module";
import { PrismaModule } from "./prisma/prisma.module";
import { UsuariosModule } from "./usuarios/usuarios.module";

@Module({
  imports: [PrismaModule, AutenticacaoModule, UsuariosModule],
})
export class AppModule {}
