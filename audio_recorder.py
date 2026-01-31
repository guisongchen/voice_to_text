#!/usr/bin/env python3
"""
Simple audio recorder that captures microphone input and saves it to a WAV file.
"""
import pyaudio
import wave
import sys
import argparse
from datetime import datetime


class AudioRecorder:
    def __init__(self, sample_rate=44100, channels=2, chunk_size=1024):
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.format = pyaudio.paInt16
        self.audio = pyaudio.PyAudio()
        
    def record(self, duration, output_file=None):
        """Record audio for specified duration in seconds"""
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"recording_{timestamp}.wav"
        
        print(f"Recording for {duration} seconds...")
        print(f"Output file: {output_file}")
        
        stream = self.audio.open(
            format=self.format,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size
        )
        
        frames = []
        total_chunks = int(self.sample_rate / self.chunk_size * duration)
        
        try:
            for i in range(total_chunks):
                data = stream.read(self.chunk_size)
                frames.append(data)
                
                progress = (i + 1) / total_chunks * 100
                print(f"\rProgress: {progress:.1f}%", end='', flush=True)
        except KeyboardInterrupt:
            print("\n\nRecording stopped by user")
        finally:
            print("\n")
            stream.stop_stream()
            stream.close()
        
        self._save_wav(frames, output_file)
        print(f"Recording saved to: {output_file}")
        return output_file
    
    def _save_wav(self, frames, filename):
        """Save recorded frames to WAV file"""
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.audio.get_sample_size(self.format))
            wf.setframerate(self.sample_rate)
            wf.writeframes(b''.join(frames))
    
    def list_devices(self):
        """List available audio input devices"""
        print("\nAvailable audio input devices:")
        print("-" * 60)
        for i in range(self.audio.get_device_count()):
            device_info = self.audio.get_device_info_by_index(i)
            if device_info['maxInputChannels'] > 0:
                print(f"Device {i}: {device_info['name']}")
                print(f"  Channels: {device_info['maxInputChannels']}")
                print(f"  Sample Rate: {int(device_info['defaultSampleRate'])} Hz")
                print()
    
    def close(self):
        """Clean up resources"""
        self.audio.terminate()


def main():
    parser = argparse.ArgumentParser(
        description="Record audio from microphone and save to WAV file"
    )
    parser.add_argument(
        '-d', '--duration',
        type=int,
        default=10,
        help='Recording duration in seconds (default: 10)'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        help='Output filename (default: recording_TIMESTAMP.wav)'
    )
    parser.add_argument(
        '-r', '--rate',
        type=int,
        default=44100,
        help='Sample rate in Hz (default: 44100)'
    )
    parser.add_argument(
        '-c', '--channels',
        type=int,
        default=2,
        choices=[1, 2],
        help='Number of channels: 1=mono, 2=stereo (default: 2)'
    )
    parser.add_argument(
        '--list-devices',
        action='store_true',
        help='List available audio input devices and exit'
    )
    
    args = parser.parse_args()
    
    recorder = AudioRecorder(
        sample_rate=args.rate,
        channels=args.channels
    )
    
    try:
        if args.list_devices:
            recorder.list_devices()
        else:
            recorder.record(args.duration, args.output)
    finally:
        recorder.close()


if __name__ == "__main__":
    main()
