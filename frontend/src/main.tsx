import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/globals.css";

// Check initial theme from localStorage
const savedTheme = localStorage.getItem("vigil-theme");
const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
if (savedTheme === "dark" || (!savedTheme && prefersDark)) {
  document.documentElement.classList.add("dark");
} else {
  document.documentElement.classList.remove("dark");
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
