/* Microphone capture + unit-scoped transcription. No expected words, no aligner. */
(function (global) {
  function preferredMime() {
    if (!global.MediaRecorder) {
      return "";
    }
    const types = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
    for (let i = 0; i < types.length; i += 1) {
      if (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(types[i])) {
        return types[i];
      }
    }
    return "";
  }

  const SpeechClient = {
    isSupported() {
      return !!(
        navigator.mediaDevices &&
        navigator.mediaDevices.getUserMedia &&
        global.MediaRecorder
      );
    },

    async startRecording() {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = preferredMime();
      const recorder = mime
        ? new MediaRecorder(stream, { mimeType: mime })
        : new MediaRecorder(stream);
      const chunks = [];
      recorder.addEventListener("dataavailable", (event) => {
        if (event.data && event.data.size) {
          chunks.push(event.data);
        }
      });
      recorder.start();
      let stopped = false;
      function stopTracks() {
        stream.getTracks().forEach((track) => {
          try {
            track.stop();
          } catch (_err) {
            /* ignore */
          }
        });
      }
      return {
        mimeType: recorder.mimeType || mime || "audio/webm",
        stop() {
          if (stopped) {
            return Promise.resolve(new Blob([], { type: recorder.mimeType || "audio/webm" }));
          }
          stopped = true;
          return new Promise((resolve, reject) => {
            recorder.addEventListener(
              "stop",
              () => {
                stopTracks();
                resolve(
                  new Blob(chunks, {
                    type: recorder.mimeType || mime || "audio/webm",
                  }),
                );
              },
              { once: true },
            );
            recorder.addEventListener(
              "error",
              () => {
                stopTracks();
                reject(new Error("recorder-error"));
              },
              { once: true },
            );
            if (recorder.state !== "inactive") {
              try {
                recorder.stop();
              } catch (_err) {
                stopTracks();
                resolve(new Blob(chunks, { type: recorder.mimeType || "audio/webm" }));
              }
            } else {
              stopTracks();
              resolve(new Blob(chunks, { type: recorder.mimeType || "audio/webm" }));
            }
          });
        },
        cancel() {
          stopped = true;
          try {
            if (recorder.state !== "inactive") {
              recorder.stop();
            }
          } catch (_err) {
            /* ignore */
          }
          stopTracks();
        },
      };
    },

    async transcribe(options) {
      const unitId = options.unitId || "";
      const body = new FormData();
      body.append("mode", options.mode || "letters");
      if (typeof options.fromIndex === "number") {
        body.append("from_index", String(options.fromIndex));
      }
      if (options.text) {
        body.append("text", options.text);
      }
      if (options.blob && options.blob.size) {
        const type = options.blob.type || "audio/webm";
        const name = type.indexOf("mp4") >= 0 ? "utterance.mp4" : "utterance.webm";
        body.append("audio", options.blob, name);
      }
      const response = await fetch(
        "/learn/" + encodeURIComponent(unitId) + "/speech/transcribe",
        {
          method: "POST",
          credentials: "same-origin",
          headers: {
            Accept: "application/json",
            "X-Requested-With": "XMLHttpRequest",
          },
          body,
          signal: options.signal,
        },
      );
      const contentType = response.headers.get("content-type") || "";
      if (!contentType.includes("application/json")) {
        const error = new Error("speech-failed");
        error.code = "provider_error";
        error.status = response.status;
        throw error;
      }
      const payload = await response.json();
      if (!response.ok || !payload || payload.ok !== true) {
        const error = new Error("speech-failed");
        error.code = (payload && payload.error) || "provider_error";
        error.status = response.status;
        throw error;
      }
      return payload;
    },
  };

  global.RecallSpeech = SpeechClient;
})(window);
