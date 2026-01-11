import os
import json
import subprocess
import asyncio
import tempfile
import shutil
import aiofiles
import aiohttp
from typing import List, Dict, Optional, Any
from fastapi import HTTPException
from models import SubtitleStyle, SubtitleItem

class VideoProcessor:
    def __init__(self, work_dir: str = None):
        self.work_dir = work_dir or tempfile.mkdtemp(prefix='video_processing_')
        os.makedirs(self.work_dir, exist_ok=True)
        self.temp_files = []
        
        # Find FFmpeg and FFprobe paths
        self.ffmpeg_path = self._find_ffmpeg()
        self.ffprobe_path = self._find_ffprobe()

    async def _run_command(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """Runs command asynchronously"""
        print(f"DEBUG: Running command: {' '.join(cmd)}")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=process.returncode,
            stdout=stdout.decode() if stdout else '',
            stderr=stderr.decode() if stderr else ''
        )
        
    def _find_ffmpeg(self) -> str:
        """Find FFmpeg executable"""
        # Check if ffmpeg is in PATH
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True)
            return 'ffmpeg'
        except FileNotFoundError:
            pass
            
        # Check local directory (Windows)
        local_ffmpeg_win = os.path.join(os.path.dirname(__file__), '..', 'ffmpeg-bin', 'ffmpeg.exe')
        if os.path.exists(local_ffmpeg_win):
            return local_ffmpeg_win
            
        # Check local directory (Linux)
        local_ffmpeg_linux = os.path.join(os.path.dirname(__file__), '..', 'ffmpeg-bin', 'ffmpeg')
        if os.path.exists(local_ffmpeg_linux):
            return local_ffmpeg_linux
            
        # Check common installation paths (Windows)
        common_paths_win = [
            r'C:\ffmpeg\bin\ffmpeg.exe',
            r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
            r'C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe'
        ]
        for path in common_paths_win:
            if os.path.exists(path):
                return path
                
        # Check common installation paths (Linux)
        common_paths_linux = [
            '/usr/bin/ffmpeg',
            '/usr/local/bin/ffmpeg',
            '/opt/ffmpeg/bin/ffmpeg'
        ]
        for path in common_paths_linux:
            if os.path.exists(path):
                return path
                
        raise FileNotFoundError("FFmpeg not found. Please install FFmpeg or place it in ffmpeg-bin directory.")
        
    def _find_ffprobe(self) -> str:
        """Find FFprobe executable"""
        # Check if ffprobe is in PATH
        try:
            subprocess.run(['ffprobe', '-version'], capture_output=True)
            return 'ffprobe'
        except FileNotFoundError:
            pass
            
        # Check local directory (Windows)
        local_ffprobe_win = os.path.join(os.path.dirname(__file__), '..', 'ffmpeg-bin', 'ffprobe.exe')
        if os.path.exists(local_ffprobe_win):
            return local_ffprobe_win
            
        # Check local directory (Linux)
        local_ffprobe_linux = os.path.join(os.path.dirname(__file__), '..', 'ffmpeg-bin', 'ffprobe')
        if os.path.exists(local_ffprobe_linux):
            return local_ffprobe_linux
            
        # Check common installation paths (Windows)
        common_paths_win = [
            r'C:\ffmpeg\bin\ffprobe.exe',
            r'C:\Program Files\ffmpeg\bin\ffprobe.exe',
            r'C:\Program Files (x86)\ffmpeg\bin\ffprobe.exe'
        ]
        for path in common_paths_win:
            if os.path.exists(path):
                return path
                
        # Check common installation paths (Linux)
        common_paths_linux = [
            '/usr/bin/ffprobe',
            '/usr/local/bin/ffprobe',
            '/opt/ffmpeg/bin/ffprobe'
        ]
        for path in common_paths_linux:
            if os.path.exists(path):
                return path
                
        raise FileNotFoundError("FFprobe not found. Please install FFmpeg or place it in ffmpeg-bin directory.")

    async def download_video(self, url: str, output_filename: str) -> Optional[str]:
        """Downloads video from URL using aiohttp"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise HTTPException(status_code=400, detail=f"Failed to download video: {url}")
                    
                    async with aiofiles.open(output_filename, 'wb') as f:
                        await f.write(await response.read())
                        
            if os.path.exists(output_filename):
                self.temp_files.append(output_filename)
                return output_filename
            return None
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error downloading video: {str(e)}")

    async def get_video_info(self, video_path: str) -> Dict[str, Any]:
        """Gets video information using ffprobe"""
        try:
            cmd = [
                self.ffprobe_path, '-v', 'quiet', '-print_format', 'json',
                '-show_streams', '-show_format', video_path
            ]
            result = await self._run_command(cmd)

            if result.returncode == 0:
                info = json.loads(result.stdout)
                video_stream = None
                audio_stream = None

                for stream in info['streams']:
                    if stream['codec_type'] == 'video' and not video_stream:
                        video_stream = stream
                    elif stream['codec_type'] == 'audio' and not audio_stream:
                        audio_stream = stream

                return {
                    'duration': float(info['format']['duration']),
                    'has_audio': audio_stream is not None,
                    'width': video_stream['width'] if video_stream else 0,
                    'height': video_stream['height'] if video_stream else 0,
                    'fps': eval(video_stream['r_frame_rate']) if video_stream else 0,
                    'file_size': os.path.getsize(video_path) / (1024 * 1024)  # Size in MB
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to get video info")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting video info: {str(e)}")

    def create_srt_subtitles(self, subtitles_data: List[SubtitleItem], output_path: str) -> str:
        """Creates SRT subtitle file"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for i, subtitle in enumerate(subtitles_data, 1):
                    f.write(f"{i}\n")
                    f.write(f"{self.format_time_srt(subtitle.start)} --> {self.format_time_srt(subtitle.end)}\n")
                    f.write(f"{subtitle.text}\n\n")

            self.temp_files.append(output_path)
            return output_path
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error creating subtitles: {str(e)}")

    def format_time_srt(self, seconds: float) -> str:
        """Converts seconds to SRT time format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

    def create_ass_karaoke_subtitles(self, subtitles_data: List[SubtitleItem], output_path: str, subtitle_style: Optional[SubtitleStyle] = None) -> str:
        """Creates ASS subtitle file with karaoke effect"""
        try:
            style = subtitle_style or SubtitleStyle()
            
            # ASS header with enhanced karaoke styling
            ass_content = """[Script Info]
Title: Karaoke Subtitles
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,Arial,12,&H00FFFFFF,&H00808080,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,2,2,30,30,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
            
            for subtitle in subtitles_data:
                start_time = self.format_time_ass(subtitle.start)
                end_time = self.format_time_ass(subtitle.end)
                
                # Calculate karaoke timing based on total duration and word count
                words = subtitle.text.split()
                total_duration = subtitle.end - subtitle.start  # Total time for the phrase
                
                if not words:
                    continue
                    
                # Calculate time per word in centiseconds
                time_per_word_cs = int((total_duration * 100) / len(words))
                
                # Set reasonable bounds: minimum 20cs (0.2s), maximum 200cs (2s) per word
                time_per_word_cs = max(20, min(200, time_per_word_cs))
                
                karaoke_text = ""
                
                for i, word in enumerate(words):
                    karaoke_text += f"{{\\k{time_per_word_cs}}}{word} "
                
                # Add karaoke dialogue line
                ass_content += f"Dialogue: 0,{start_time},{end_time},Karaoke,,0,0,0,karaoke,{karaoke_text.strip()}\n"
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(ass_content)
            
            self.temp_files.append(output_path)
            return output_path
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error creating karaoke subtitles: {str(e)}")

    def format_time_ass(self, seconds: float) -> str:
        """Converts seconds to ASS time format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:05.2f}"

    async def merge_videos(
        self,
        video_urls: List[str],
        music_path: Optional[str] = None,
        subtitles_data: Optional[List[SubtitleItem]] = None,
        karaoke_mode: bool = False,
        subtitle_style: Optional[SubtitleStyle] = None,
        output_filename: str = "merged_video.mp4",
        progress_callback: Optional[callable] = None
    ) -> str:
        """Main function for merging videos with music and subtitles"""
        downloaded_videos = []
        try:
            if progress_callback:
                await progress_callback(5.0)

            # Download all videos
            for i, url in enumerate(video_urls):
                video_filename = os.path.join(self.work_dir, f"video_{i+1}.mp4")
                if downloaded := await self.download_video(url, video_filename):
                    downloaded_videos.append(downloaded)
            
            if progress_callback:
                await progress_callback(20.0)

            if not downloaded_videos:
                raise HTTPException(status_code=400, detail="No videos were downloaded successfully")

            # Create concat file
            concat_file = os.path.join(self.work_dir, "concat_list.txt")
            with open(concat_file, 'w') as f:
                for video in downloaded_videos:
                    f.write(f"file '{video}'\n")
            self.temp_files.append(concat_file)

            # Merge videos (preserving audio if present)
            merged_video_base = os.path.join(self.work_dir, "merged_base.mp4")
            cmd_concat = [
                self.ffmpeg_path, '-f', 'concat', '-safe', '0', '-i', concat_file,
                '-c:v', 'copy', '-c:a', 'aac', '-strict', 'experimental', merged_video_base, '-y'
            ]
            print(f"DEBUG: Running FFmpeg command: {' '.join(cmd_concat)}")
            print(f"DEBUG: Concat file content:")
            with open(concat_file, 'r') as f:
                print(f.read())
            result = await self._run_command(cmd_concat)
            if result.returncode != 0:
                print(f"DEBUG: FFmpeg stderr: {result.stderr}")
                print(f"DEBUG: FFmpeg stdout: {result.stdout}")
                raise HTTPException(status_code=500, detail=f"Error merging videos: {result.stderr}")
            
            self.temp_files.append(merged_video_base)
            current_video = merged_video_base

            if progress_callback:
                await progress_callback(40.0)

            # Add subtitles if provided
            if subtitles_data:
                print(f"DEBUG: Adding subtitles, data: {subtitles_data}, karaoke_mode: {karaoke_mode}")
                
                if karaoke_mode:
                    # Create ASS file for karaoke effect
                    subtitle_file = os.path.join(self.work_dir, "subtitles.ass")
                    self.create_ass_karaoke_subtitles(subtitles_data, subtitle_file, subtitle_style)
                else:
                    # Create regular SRT file
                    subtitle_file = os.path.join(self.work_dir, "subtitles.srt")
                    self.create_srt_subtitles(subtitles_data, subtitle_file)
                
                if progress_callback:
                    await progress_callback(50.0)

                print(f"DEBUG: Created subtitle file: {subtitle_file}")
                with open(subtitle_file, 'r', encoding='utf-8') as f:
                    print(f"DEBUG: Subtitle file content:\n{f.read()}")
                
                video_with_subtitles = os.path.join(self.work_dir, "video_with_subtitles.mp4")
                
                if karaoke_mode:
                    # For ASS files, use ass filter
                    cmd_sub = [
                        self.ffmpeg_path, '-i', current_video, '-vf',
                        f"ass={subtitle_file}",
                        '-c:a', 'copy', video_with_subtitles, '-y'
                    ]
                else:
                    # For SRT files, use subtitles filter with styling
                    style = subtitle_style or SubtitleStyle()
                    cmd_sub = [
                        self.ffmpeg_path, '-i', current_video, '-vf',
                        f"subtitles={subtitle_file}:force_style='FontName={style.font_name},FontSize={style.font_size},"
                        f"PrimaryColour={style.font_color},BackColour={style.background_color},Bold={1 if style.bold else 0},"
                        f"Alignment={style.alignment},MarginV={style.margin_v}'",
                        '-c:a', 'copy', video_with_subtitles, '-y'
                    ]
                
                print(f"DEBUG: Running subtitle command: {' '.join(cmd_sub)}")
                result = await self._run_command(cmd_sub)
                print(f"DEBUG: Subtitle command result: returncode={result.returncode}")
                if result.stderr:
                    print(f"DEBUG: Subtitle stderr: {result.stderr}")
                if result.returncode == 0:
                    current_video = video_with_subtitles
                    self.temp_files.append(video_with_subtitles)
                    print(f"DEBUG: Successfully added subtitles to video")
                else:
                    print(f"DEBUG: Failed to add subtitles: {result.stderr}")
                
                if progress_callback:
                    await progress_callback(70.0)
            else:
                print("DEBUG: No subtitles data provided")

            if music_path:
                # Get video duration for music loop
                video_info = await self.get_video_info(current_video)
                video_duration = video_info['duration']
                has_original_audio = video_info.get('has_audio', False)

                # Prepare music
                prepared_audio = os.path.join(self.work_dir, "prepared_audio.mp3")
                cmd_audio = [
                    self.ffmpeg_path, '-stream_loop', '-1', '-i', music_path,
                    '-t', str(video_duration), '-acodec', 'libmp3lame',
                    '-ab', '128k', prepared_audio, '-y'
                ]
                result = await self._run_command(cmd_audio)
                if result.returncode != 0:
                    raise HTTPException(status_code=500, detail=f"Error preparing audio: {result.stderr}")
                
                self.temp_files.append(prepared_audio)
                
                if progress_callback:
                    await progress_callback(80.0)

                # Final merge with music
                final_output = os.path.join(self.work_dir, output_filename)
                
                # Use music as the only audio, replacing original audio if present
                cmd_final = [
                    self.ffmpeg_path, '-i', current_video, '-i', prepared_audio,
                    '-map', '0:v', '-map', '1:a',
                    '-c:v', 'libx264', '-c:a', 'aac', '-strict', 'experimental',
                    '-shortest', final_output, '-y'
                ]
                
                result = await self._run_command(cmd_final)
                if result.returncode != 0:
                    raise HTTPException(status_code=500, detail=f"Error creating final video: {result.stderr}")
            else:
                # No music, just copy current video to final output
                final_output = os.path.join(self.work_dir, output_filename)
                cmd_final = [
                    self.ffmpeg_path, '-i', current_video,
                    '-c', 'copy', final_output, '-y'
                ]
                result = await self._run_command(cmd_final)
                if result.returncode != 0:
                    raise HTTPException(status_code=500, detail=f"Error creating final video: {result.stderr}")

            if progress_callback:
                await progress_callback(95.0)

            return final_output

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing video: {str(e)}")

    async def process_circle_video(
        self,
        background_video_url: str,
        circle_video_url: str,
        background_volume: float = 1.0,
        circle_volume: float = 1.0,
        output_filename: str = "circle_video.mp4",
        progress_callback: Optional[callable] = None
    ) -> str:
        """Processes video with a circle overlay"""
        try:
            if progress_callback:
                await progress_callback(5.0)

            # 1. Download videos
            bg_video_path = os.path.join(self.work_dir, "background.mp4")
            circle_video_path = os.path.join(self.work_dir, "circle.mp4")
            
            if not await self.download_video(background_video_url, bg_video_path):
                 raise HTTPException(status_code=400, detail="Failed to download background video")
            
            if progress_callback:
                await progress_callback(15.0)

            if not await self.download_video(circle_video_url, circle_video_path):
                 raise HTTPException(status_code=400, detail="Failed to download circle video")

            if progress_callback:
                await progress_callback(30.0)

            # Get info for circle video to determine duration
            circle_info = await self.get_video_info(circle_video_path)
            duration = circle_info.get('duration', 0)

            # 2. Construct FFmpeg command
            output_path = os.path.join(self.work_dir, output_filename)
            
            # Filter complex explanation:
            # [1:v][0:v]scale2ref=w=iw*0.6:h=iw*0.6[over][bg] -> Scale overlay to 60% of bg width, force square (1:1)
            # [over]format=yuva420p,geq=...[circular] -> Create circular mask
            # [bg][circular]overlay=x=W-w-20:y=H-h-20[v] -> Overlay at bottom right
            # Audio mixing
            
            filter_complex = (
                f"[1:v][0:v]scale2ref=w=iw*0.6:h=iw*0.6[over][bg];"
                f"[over]format=yuva420p,geq=lum='p(X,Y)':a='if(lte(pow(X-W/2,2)+pow(Y-H/2,2),pow(min(W,H)/2,2)),255,0)'[circular];"
                f"[bg][circular]overlay=x=W-w-20:y=H-h-20[v];"
                f"[0:a]volume={background_volume}[a0];"
                f"[1:a]volume={circle_volume}[a1];"
                f"[a0][a1]amix=inputs=2:duration=first[a]"
            )

            cmd = [
                self.ffmpeg_path,
                '-i', bg_video_path,
                '-i', circle_video_path,
                '-filter_complex', filter_complex,
                '-map', '[v]',
                '-map', '[a]',
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-c:a', 'aac',
                '-t', str(duration),
                output_path,
                '-y'
            ]
            
            print(f"DEBUG: Running FFmpeg command: {' '.join(cmd)}")
            result = await self._run_command(cmd)
            
            if result.returncode != 0:
                print(f"DEBUG: FFmpeg stderr: {result.stderr}")
                raise HTTPException(status_code=500, detail=f"FFmpeg conversion failed: {result.stderr}")

            if progress_callback:
                await progress_callback(100.0)
                
            return output_path

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing video: {str(e)}")

    def cleanup(self):
        """Cleans up temporary files"""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass
        try:
            if os.path.exists(self.work_dir):
                shutil.rmtree(self.work_dir)
        except:
            pass

    def check_ffmpeg(self) -> Optional[str]:
        """Checks if FFmpeg is installed and returns version"""
        try:
            result = subprocess.run([self.ffmpeg_path, '-version'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.split('\\n')[0]
            return None
        except:
            return None
