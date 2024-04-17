cd /usr/src/app

if [ "$DEVELOPMENT" == "true" ]
    then
        npm run start:dev
    else
        npm run start
fi

