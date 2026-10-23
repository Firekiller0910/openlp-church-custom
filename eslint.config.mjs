import { defineConfig } from "eslint/config";
import js from "@eslint/js";

export default defineConfig([
	js.configs.recommended,
	{
		rules: {
			"indent": "warn",
            "no-prototype-builtins": "warn",
            "no-undef": "warn",
			"no-unused-vars": "warn",
            "no-useless-assignment": "warn",
		},
	},
]);