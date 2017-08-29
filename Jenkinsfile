#!groovy 
pipeline {
    agent {
        label 'master'
    }
    stages {
        stage('Build') {            
            steps {                
                def scmVars = checkout scm
                def commitHash = scmVars.GIT_COMMIT
                echo scmVars
                echo 'Building'            
                echo 'Building'            
            }        
        }        
        stage('Test') {            
            steps {                
                echo 'Testing'            
            }        
        }
        stage('Deploy - Staging') {            
            steps {                
                echo './deploy staging'                
                echo './run-smoke-tests'            
            }        
        }        
        stage('Sanity check') {            
            steps {                
                input "Does the staging environment look ok?"            
            }        
        }        
        stage('Deploy - Production') {            
            steps {                
                echo './deploy production'            
            }        
        }    
    }

    post {        
        always {            
            echo 'One way or another, I have fiechoshed'            
            deleteDir() /* clean up our workspace */        
        }        
        success {            
            echo 'I succeeeded!'        
        }        
        unstable {            
            echo 'I am unstable :/'        
            echo 'I am unstable :/'        
        }        
        failure {            
            echo 'I failed :('        
        }        
        changed {            
            echo 'Things were different before...'        
        }    
    }
}
