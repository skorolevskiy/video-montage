import os
import json
import subprocess
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

    def get_video_info(self, video_path: str) -> Dict[str, Any]:
        """Gets video information using ffprobe"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_streams', '-show_format', video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)

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
                    f.write(f"{i}\\n")
                    f.write(f"{self.format_time_srt(subtitle.start)} --> {self.format_time_srt(subtitle.end)}\\n")
                    f.write(f"{subtitle.text}\\n\\n")

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

    async def merge_videos(
        self,
        video_urls: List[str],
        music_path: str,
        subtitles_data: Optional[List[SubtitleItem]] = None,
        karaoke_mode: bool = False,
        subtitle_style: Optional[SubtitleStyle] = None,
        output_filename: str = "merged_video.mp4"
    ) -> str:
        """Main function for merging videos with music and subtitles"""
        downloaded_videos = []
        try:
            # Download all videos
            for i, url in enumerate(video_urls):
                video_filename = os.path.join(self.work_dir, f"video_{i+1}.mp4")
                if downloaded := await self.download_video(url, video_filename):
                    downloaded_videos.append(downloaded)

            if not downloaded_videos:
                raise HTTPException(status_code=400, detail="No videos were downloaded successfully")

            # Create concat file
            concat_file = os.path.join(self.work_dir, "concat_list.txt")
            with open(concat_file, 'w') as f:
                for video in downloaded_videos:
                    f.write(f"file '{video}'\\n")
            self.temp_files.append(concat_file)

            # Merge videos without audio
            merged_video_no_audio = os.path.join(self.work_dir, "merged_no_audio.mp4")
            cmd_concat = [
                'ffmpeg', '-f', 'concat', '-safe', '0', '-i', concat_file,
                '-c', 'copy', '-an', merged_video_no_audio, '-y'
            ]
            result = subprocess.run(cmd_concat, capture_output=True, text=True)
            if result.returncode != 0:
                raise HTTPException(status_code=500, detail=f"Error merging videos: {result.stderr}")
            
            self.temp_files.append(merged_video_no_audio)
            current_video = merged_video_no_audio

            # Add subtitles if provided
            if subtitles_data:
                subtitle_file = os.path.join(self.work_dir, "subtitles.srt")
                self.create_srt_subtitles(subtitles_data, subtitle_file)
                
                video_with_subtitles = os.path.join(self.work_dir, "video_with_subtitles.mp4")
                style = subtitle_style or SubtitleStyle()
                
                cmd_sub = [
                    'ffmpeg', '-i', current_video, '-vf',
                    f"subtitles={subtitle_file}:force_style='FontName={style.font_name},FontSize={style.font_size},"
                    f"PrimaryColour={style.font_color},BackColour={style.background_color},Bold={1 if style.bold else 0},"
                    f"Alignment={style.alignment},MarginV={style.margin_v}'",
                    '-c:a', 'copy', video_with_subtitles, '-y'
                ]
                
                result = subprocess.run(cmd_sub, capture_output=True, text=True)
                if result.returncode == 0:
                    current_video = video_with_subtitles
                    self.temp_files.append(video_with_subtitles)

            # Get video duration for music loop
            video_info = self.get_video_info(current_video)
            video_duration = video_info['duration']

            # Prepare music
            prepared_audio = os.path.join(self.work_dir, "prepared_audio.mp3")
            cmd_audio = [
                'ffmpeg', '-stream_loop', '-1', '-i', music_path,
                '-t', str(video_duration), '-acodec', 'libmp3lame',
                '-ab', '128k', prepared_audio, '-y'
            ]
            result = subprocess.run(cmd_audio, capture_output=True, text=True)
            if result.returncode != 0:
                raise HTTPException(status_code=500, detail=f"Error preparing audio: {result.stderr}")
            
            self.temp_files.append(prepared_audio)

            # Final merge with music
            final_output = os.path.join(self.work_dir, output_filename)
            cmd_final = [
                'ffmpeg', '-i', current_video, '-i', prepared_audio,
                '-c:v', 'libx264', '-c:a', 'aac', '-strict', 'experimental',
                '-shortest', final_output, '-y'
            ]
            result = subprocess.run(cmd_final, capture_output=True, text=True)
            if result.returncode != 0:
                raise HTTPException(status_code=500, detail=f"Error creating final video: {result.stderr}")

            return final_output

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
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.split('\\n')[0]
            return None
        except:
            return None
