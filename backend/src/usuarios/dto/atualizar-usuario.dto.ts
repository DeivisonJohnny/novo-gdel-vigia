import { IsBoolean, IsIn, IsOptional, IsString, Length } from "class-validator";
import { PAPEIS, type Papel } from "./papel-usuario";

export class AtualizarUsuarioDto {
  @IsOptional()
  @IsString()
  @Length(2, 120)
  nome?: string;

  @IsOptional()
  @IsIn(PAPEIS)
  papel?: Papel;

  @IsOptional()
  @IsBoolean()
  ativo?: boolean;

  @IsOptional()
  @IsString()
  senha?: string;
}
