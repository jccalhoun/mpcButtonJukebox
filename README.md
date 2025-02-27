# mpcButtonJukebox
A python script for running a Jukebox with a raspberry pi 5 that uses song numbers to add songs to the mpc queue and displays album art in a gtk window

Other scripts for running a jukebox from a raspberry pi use a touch screen to select songs. I wanted to be able to pick the songs using the buttons on the jukebox so I cobbled this together. 

I'm not programmer so this was greatly assisted by chatgpt and other ai tools. 

Only plays local music files and only looks inside the files for the album art. 
Displays the numbers as entered on one 4 digit 7-segment diplay and the number of songs in the queue on a second
once a 4 digit number has been input the script looks up that line number from a txt file and ads it to the mpd queue. Adds without hitting enter. 

album art based on https://github.com/dedenholm/mpd-Coverview-kitty 
