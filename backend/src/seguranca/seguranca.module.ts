import { Module } from "@nestjs/common";
import { LimiteDeTentativasService } from "./limite-de-tentativas.service";
import { SegurancaService } from "./seguranca.service";

@Module({
  providers: [SegurancaService, LimiteDeTentativasService],
  exports: [SegurancaService, LimiteDeTentativasService],
})
export class SegurancaModule {}
