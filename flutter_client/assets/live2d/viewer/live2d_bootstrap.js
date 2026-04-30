(function () {
  const MOTION_GROUPS = [
    "Idle",
    "Tap",
    "Flick",
    "FlickUp",
    "FlickDown",
    "Tap@Body",
    "Flick@Body",
  ];

  const state = {
    app: null,
    model: null,
    scale: 1,
  };

  function notify(payload) {
    if (typeof window.__live2dNotifyFlutter === "function") {
      window.__live2dNotifyFlutter(payload);
    }
  }

  function resizeModel() {
    if (!state.app || !state.model) {
      return;
    }

    const width = state.app.renderer.width;
    const height = state.app.renderer.height;
    const scale = Math.min(width / 1100, height / 1500) * state.scale;

    state.model.anchor.set(0.5, 1);
    state.model.position.set(width * 0.54, height * 0.97);
    state.model.scale.set(scale);
  }

  async function playMotion(group) {
    if (!state.model) {
      return;
    }

    const motionGroup = MOTION_GROUPS.includes(group) ? group : "Idle";
    try {
      await state.model.motion(motionGroup, 0);
      notify({ type: "motionChanged", motion: motionGroup });
    } catch (error) {
      console.warn("Failed to play motion", motionGroup, error);
    }
  }

  function playRandomMotion() {
    const motionGroup = MOTION_GROUPS[Math.floor(Math.random() * MOTION_GROUPS.length)];
    return playMotion(motionGroup);
  }

  function setScale(scale) {
    state.scale = Number(scale) || 1;
    resizeModel();
  }

  async function boot() {
    const canvas = document.getElementById("stage");
    const app = new PIXI.Application({
      view: canvas,
      transparent: true,
      autoStart: true,
      antialias: true,
      resizeTo: window,
      autoDensity: true,
      resolution: window.devicePixelRatio || 1,
    });

    window.PIXI = PIXI;
    const model = await PIXI.live2d.Live2DModel.from(
      "/runtime/hiyori_pro_t11.model3.json"
    );

    model.interactive = true;
    model.buttonMode = true;
    model.on("pointertap", () => {
      playRandomMotion();
    });
    model.on("hit", (hitAreas) => {
      if (Array.isArray(hitAreas) && hitAreas.includes("Body")) {
        playMotion("Tap@Body");
      }
    });

    app.stage.addChild(model);

    state.app = app;
    state.model = model;
    resizeModel();
    window.addEventListener("resize", resizeModel);

    await playMotion("Idle");
    notify({ type: "ready", motionGroups: MOTION_GROUPS });
  }

  window.live2dDesktopPet = {
    playMotion,
    playRandomMotion,
    setScale,
  };

  boot().catch((error) => {
    console.error("Live2D bootstrap failed", error);
    notify({
      type: "error",
      message: error && error.message ? error.message : String(error),
    });
  });
})();
