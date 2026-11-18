// onnx-hybrid-loader.js — Integración automática de MobileNetV2 (.onnx) en el navegador para AquaVigía
// Carga mobilenet_etapa1_riesgo.onnx y mobilenet_etapa2_larva.onnx usando ONNX Runtime Web
(function () {
  window.AquaVigiaONNX = {
    session1: null,
    session2: null,
    ready: false,
    async init() {
      if (typeof ort === "undefined") return false;
      try {
        ort.env.wasm.wasmPaths = "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.19.2/dist/";
        const [s1, s2] = await Promise.all([
          ort.InferenceSession.create("./mobilenet_etapa1_riesgo.onnx", { executionProviders: ["wasm"] }),
          ort.InferenceSession.create("./mobilenet_etapa2_larva.onnx", { executionProviders: ["wasm"] })
        ]);
        this.session1 = s1;
        this.session2 = s2;
        this.ready = true;
        console.log("[AquaVigía ONNX] MobileNetV2 Etapa 1 y Etapa 2 cargados correctamente.");
        return true;
      } catch (err) {
        console.warn("[AquaVigía ONNX] Usando motor híbrido RBF de respaldo:", err);
        return false;
      }
    },
    async predict(imgElement) {
      if (!this.ready) await this.init();
      if (!this.ready) return null;
      const c = document.createElement("canvas");
      c.width = 128; c.height = 128;
      const ctx = c.getContext("2d");
      ctx.drawImage(imgElement, 0, 0, 128, 128);
      const rgba = ctx.getImageData(0, 0, 128, 128).data;
      const rgbFloat = new Float32Array(1 * 128 * 128 * 3);
      for (let i = 0; i < 128 * 128; i++) {
        rgbFloat[i * 3]     = rgba[i * 4];
        rgbFloat[i * 3 + 1] = rgba[i * 4 + 1];
        rgbFloat[i * 3 + 2] = rgba[i * 4 + 2];
      }
      const tensor = new ort.Tensor("float32", rgbFloat, [1, 128, 128, 3]);
      const out1 = await this.session1.run({ "input_layer_1:0": tensor });
      const out2 = await this.session2.run({ "input_layer_4:0": tensor });
      const probRisk = out1["Identity:0"].data[0];
      const probLarva = out2["Identity:0"].data[0];
      return { probRisk, probLarva };
    }
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => window.AquaVigiaONNX.init());
  } else {
    window.AquaVigiaONNX.init();
  }
})();
