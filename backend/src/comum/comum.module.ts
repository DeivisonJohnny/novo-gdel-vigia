import { Module } from "@nestjs/common";
import { SegurancaModule } from "../seguranca/seguranca.module";
import { AdminGuard } from "./guards/admin.guard";
import { SessaoGuard } from "./guards/sessao.guard";

@Module({
  imports: [SegurancaModule],
  providers: [SessaoGuard, AdminGuard],
  exports: [SessaoGuard, AdminGuard],
})
export class ComumModule {}
