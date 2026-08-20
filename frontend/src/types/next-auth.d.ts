import { DefaultSession } from "next-auth";

declare module "next-auth" {
  interface Session extends DefaultSession {
    backendToken?: string;
    familyId?: string;
    baseCurrency?: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    backendToken?: string;
    familyId?: string;
    baseCurrency?: string;
  }
}
