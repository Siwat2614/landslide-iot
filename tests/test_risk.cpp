#include "../firmware/landslide_esp8266/risk_rules.h"
#include <cassert>
#include <string>
#include <iostream>
int main(){int n=0;for(int soil: {0,59,60,79,80,100})for(int r=0;r<2;r++)for(int v=0;v<2;v++)for(int m=0;m<2;m++){
int score=(soil>=60)+(soil>=80)+r+v+2*m;const char* expected=score>=4?"DANGER":score>=2?"WARNING":"NORMAL";
assert(std::string(classifyRisk(soil,r,v,m))==expected);n++;}std::cout<<n<<" risk boundary combinations: PASS\n";}
