#pragma once
inline const char* classifyRisk(int soil, bool rain, bool vibration, bool movement, int warning=60, int danger=80) {
  int score=(soil>=warning)+(soil>=danger)+rain+vibration+(movement?2:0);
  if(score>=4)return "DANGER";
  if(score>=2)return "WARNING";
  return "NORMAL";
}
