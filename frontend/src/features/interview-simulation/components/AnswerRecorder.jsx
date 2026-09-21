// src/features/interview-simulation/components/AnswerRecorder.jsx
import { useRef, useState, useEffect } from "react";
import { interviewApi } from "../api";

export default function AnswerRecorder({ sessionId, onSubmitAnswer, loading }) {
  const [recording, setRecording] = useState(false);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const frameIntervalRef = useRef(null);

  const captureFrame = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.videoWidth === 0) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);

    canvas.toBlob(
      (blob) => {
        if (blob) interviewApi.submitEmotionFrame(sessionId, blob);
      },
      "image/jpeg",
      0.8
    );
  };

  const startRecording = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: true });
    streamRef.current = stream;

    if (videoRef.current) {
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
    }

    // Record only the audio track — video is just for emotion frame snapshots
    const audioOnlyStream = new MediaStream(stream.getAudioTracks());
    const recorder = new MediaRecorder(audioOnlyStream);
    chunksRef.current = [];

    recorder.ondataavailable = (e) => chunksRef.current.push(e.data);
    recorder.onstop = () => {
      clearInterval(frameIntervalRef.current);
      const blob = new Blob(chunksRef.current, { type: "audio/webm" });
      onSubmitAnswer(blob);
      stream.getTracks().forEach((t) => t.stop());
    };

    recorder.start();
    mediaRecorderRef.current = recorder;
    frameIntervalRef.current = setInterval(captureFrame, 2000); // one frame every 2s
    setRecording(true);
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    setRecording(false);
  };

  useEffect(() => {
    return () => {
      clearInterval(frameIntervalRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  return (
    <div className="answer-recorder">
      <video ref={videoRef} muted />
      <canvas ref={canvasRef} style={{ display: "none" }} />
      {!recording ? (
        <button className="btn-record" onClick={startRecording} disabled={loading}>Start Answer</button>
      ) : (
        <button className="btn-stop" onClick={stopRecording}>Stop Answer</button>
      )}
      {loading && <p className="processing-note">Processing your answer...</p>}
    </div>
  );
}