import React, {
  useEffect,
  useRef,
  useState,
  useImperativeHandle,
  forwardRef,
} from "react";
import WaveSurfer from "wavesurfer.js";
import { Play, Pause, RotateCcw, FastForward, Rewind, Volume2, VolumeX } from "lucide-react";
import { cn } from "../../lib/utils";

export interface AudioPlayerRef {
  seekTo: (seconds: number) => void;
  play: () => void;
  pause: () => void;
  getCurrentTime: () => number;
}

interface AudioPlayerProps {
  audioUrl?: string;
  className?: string;
  onTimeUpdate?: (currentTime: number) => void;
  violationStart?: number; // In seconds, to display a visual marker
  violationEnd?: number;
}

export const AudioPlayer = forwardRef<AudioPlayerRef, AudioPlayerProps>(
  (
    {
      audioUrl = "/audio/sample_call.wav",
      className,
      onTimeUpdate,
      violationStart,
      violationEnd,
    },
    ref
  ) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const waveSurferRef = useRef<WaveSurfer | null>(null);
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);
    const [isMuted, setIsMuted] = useState(false);
    const [isReady, setIsReady] = useState(false);

    const formatTime = (secs: number) => {
      if (isNaN(secs)) return "00:00";
      const m = Math.floor(secs / 60);
      const s = Math.floor(secs % 60);
      return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
    };

    useEffect(() => {
      if (!containerRef.current) return;

      const isDarkMode = document.documentElement.classList.contains("dark");

      const ws = WaveSurfer.create({
        container: containerRef.current,
        waveColor: isDarkMode ? "#475569" : "#cbd5e1",
        progressColor: isDarkMode ? "#38bdf8" : "#0f172a",
        cursorColor: "#ef4444",
        cursorWidth: 2,
        height: 68,
        barWidth: 3,
        barGap: 2,
        barRadius: 3,
        url: audioUrl,
      });

      waveSurferRef.current = ws;

      ws.on("ready", () => {
        setIsReady(true);
        setDuration(ws.getDuration());
      });

      ws.on("timeupdate", (time) => {
        setCurrentTime(time);
        if (onTimeUpdate) {
          onTimeUpdate(time);
        }
      });

      ws.on("play", () => setIsPlaying(true));
      ws.on("pause", () => setIsPlaying(false));
      ws.on("finish", () => {
        setIsPlaying(false);
        setCurrentTime(0);
      });

      return () => {
        ws.destroy();
        waveSurferRef.current = null;
      };
    }, [audioUrl]);

    useImperativeHandle(ref, () => ({
      seekTo: (seconds: number) => {
        if (!waveSurferRef.current) return;
        const dur = waveSurferRef.current.getDuration() || duration || 135;
        const progress = Math.min(Math.max(seconds / dur, 0), 1);
        waveSurferRef.current.seekTo(progress);
        setCurrentTime(seconds);
        // Automatically start playing when user seeks to evidence
        waveSurferRef.current.play();
      },
      play: () => waveSurferRef.current?.play(),
      pause: () => waveSurferRef.current?.pause(),
      getCurrentTime: () => waveSurferRef.current?.getCurrentTime() || 0,
    }));

    const togglePlay = () => {
      if (!waveSurferRef.current) return;
      waveSurferRef.current.playPause();
    };

    const skipTime = (delta: number) => {
      if (!waveSurferRef.current) return;
      const cur = waveSurferRef.current.getCurrentTime();
      const dur = waveSurferRef.current.getDuration() || duration || 1;
      const target = Math.min(Math.max(cur + delta, 0), dur);
      waveSurferRef.current.seekTo(target / dur);
    };

    const toggleMute = () => {
      if (!waveSurferRef.current) return;
      const nextMute = !isMuted;
      waveSurferRef.current.setMuted(nextMute);
      setIsMuted(nextMute);
    };

    // Calculate violation range percentage on the waveform for a marker overlay
    const hasViolationRange =
      violationStart !== undefined &&
      violationEnd !== undefined &&
      duration > 0;
    const markerLeftPercent = hasViolationRange
      ? `${(violationStart / duration) * 100}%`
      : undefined;
    const markerWidthPercent = hasViolationRange
      ? `${((violationEnd - violationStart) / duration) * 100}%`
      : undefined;

    return (
      <div
        className={cn(
          "bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-4 shadow-sm",
          className
        )}
      >
        {/* Waveform container with potential violation region indicator */}
        <div className="relative mb-3 bg-slate-50 dark:bg-slate-950/50 rounded-md p-2 border border-slate-100 dark:border-slate-800/80">
          <div ref={containerRef} className="w-full" />

          {/* Violation time marker overlay */}
          {hasViolationRange && markerLeftPercent && (
            <div
              className="absolute top-0 bottom-0 bg-red-500/20 border-x-2 border-red-500 pointer-events-none transition-all"
              style={{
                left: markerLeftPercent,
                width: markerWidthPercent,
              }}
              title="Detected violation segment"
            >
              <div className="absolute -top-2 left-0 -translate-x-1/2 bg-red-600 text-white text-[10px] font-mono px-1.5 py-0.5 rounded shadow">
                FLAG
              </div>
            </div>
          )}
        </div>

        {/* Player controls */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <button
              onClick={() => skipTime(-10)}
              className="p-1.5 text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-800 rounded transition-colors"
              title="Rewind 10s"
              type="button"
            >
              <Rewind className="w-4 h-4" />
            </button>

            <button
              onClick={togglePlay}
              disabled={!isReady}
              className={cn(
                "w-10 h-10 flex items-center justify-center rounded-full transition-colors",
                isPlaying
                  ? "bg-slate-900 text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900"
                  : "bg-red-600 text-white hover:bg-red-700 shadow-sm"
              )}
              title={isPlaying ? "Pause audio" : "Play audio"}
              type="button"
            >
              {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5 ml-0.5" />}
            </button>

            <button
              onClick={() => skipTime(10)}
              className="p-1.5 text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-800 rounded transition-colors"
              title="Fast forward 10s"
              type="button"
            >
              <FastForward className="w-4 h-4" />
            </button>

            <button
              onClick={() => {
                if (waveSurferRef.current) {
                  waveSurferRef.current.seekTo(0);
                }
              }}
              className="p-1.5 text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-800 rounded transition-colors"
              title="Restart from beginning"
              type="button"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          </div>

          {/* Time Counter */}
          <div className="flex items-center gap-1.5 font-mono text-sm tracking-wider text-slate-700 dark:text-slate-300">
            <span className="font-semibold text-slate-900 dark:text-slate-100">
              {formatTime(currentTime)}
            </span>
            <span className="text-slate-400">/</span>
            <span>{formatTime(duration || 135)}</span>
          </div>

          {/* Audio volume */}
          <div className="flex items-center gap-2">
            <button
              onClick={toggleMute}
              className="p-1.5 text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-800 rounded transition-colors"
              type="button"
            >
              {isMuted ? <VolumeX className="w-4 h-4 text-red-500" /> : <Volume2 className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </div>
    );
  }
);

AudioPlayer.displayName = "AudioPlayer";
