import { IsEmail, IsIn, IsOptional, IsString, Length } from "class-validator";
import { PAPEIS, type Papel } from "./papel-usuario";

export class CriarUsuarioDto {
  @IsString()
  @Length(2, 120)
  nome!: string;

  @IsEmail()
  @Length(5, 200)
  email!: string;

  @IsOptional()
  @IsIn(PAPEIS)
  papel: Papel = "operador";

  @IsString()
  senha!: string;
}
