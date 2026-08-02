import nextVitals from "eslint-config-next/core-web-vitals";

const config = [
  { ignores: ["outputs/**", "local_data/**", ".next/**", "node_modules/**"] },
  ...nextVitals,
  {
    rules: {
      "react-hooks/set-state-in-effect": "off",
      "@next/next/no-img-element": "off"
    }
  }
];

export default config;
